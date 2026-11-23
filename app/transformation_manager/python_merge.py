"""
Merge python implementations that pass objects to each other into one service.

Python implementations become Camunda external service tasks that exchange their
``@input`` / ``@output`` variables as process variables, i.e. as numbers, strings or JSON.
Objects (e.g. a Qiskit ``QuadraticProgram``) cannot be passed this way. If a python node
passes an object (see :func:`~app.transformation_manager.python_service.object_variables`)
to another python node, both nodes are merged into one python node whose code runs the
blocks one after the other (``# @part <label>``), so the object stays in memory.

Before, the ``@property`` annotations are resolved with the property values of the
nodes (see :func:`~app.transformation_manager.python_service.resolve_properties`).
"""

from __future__ import annotations

from collections import defaultdict, deque

from app.model.CompileRequest import CompileRequest, Edge, ImplementationNode
from app.transformation_manager.python_service import (
    PythonAnnotationError,
    PythonServiceInterface,
    is_python_implementation,
    merge_requirements,
    object_variables,
    parse_python_implementation,
    resolve_properties,
)


def prepare_python_nodes(request: CompileRequest) -> CompileRequest:
    """
    Resolve the properties of the python nodes and merge the python nodes that
    pass objects to each other (see :func:`merge_object_blocks`).
    """
    return merge_object_blocks(resolve_python_properties(request))


def resolve_python_properties(request: CompileRequest) -> CompileRequest:
    """
    Write the property values of the python nodes into their code.

    Invalid code is kept as it is, its error is reported when the services are generated.
    """
    changed = False
    nodes = []
    for node in request.nodes:
        if is_python_implementation(node) and "@property" in node.implementation:
            assert isinstance(node, ImplementationNode)
            try:
                code = resolve_properties(node.implementation, node.propertyValues)
            except PythonAnnotationError:
                code = node.implementation
            if code != node.implementation:
                node = node.model_copy(
                    update={"implementation": code, "propertyValues": None}
                )
                changed = True
        nodes.append(node)
    return request.model_copy(update={"nodes": nodes}) if changed else request


def _object_edges(
    request: CompileRequest,
    python_nodes: dict[str, ImplementationNode],
    interfaces: dict[str, PythonServiceInterface],
) -> list[tuple[str, str]]:
    """Edges between python nodes over which an object is passed."""
    objects = {
        node_id: object_variables(node.implementation)
        for node_id, node in python_nodes.items()
    }
    result = []
    for edge in request.edges:
        source, target = edge.source[0], edge.target[0]
        if source == target or source not in python_nodes or target not in python_nodes:
            continue
        shared = set(interfaces[source].outputs) & set(interfaces[target].inputs)
        if shared & (objects[source] | objects[target]):
            result.append((source, target))
    return result


def _groups(node_ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Connected components (union-find) with more than one node, in node order."""
    parent = {node_id: node_id for node_id in node_ids}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    for source, target in edges:
        parent[find(source)] = find(target)

    components: dict[str, list[str]] = defaultdict(list)
    for node_id in node_ids:
        components[find(node_id)].append(node_id)
    return [members for members in components.values() if len(members) > 1]


def _reachable(start: set[str], successors: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque(start)
    while queue:
        for successor in successors[queue.popleft()]:
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)
    return seen


def _creates_cycle(members: set[str], request: CompileRequest) -> bool:
    """
    Whether merging the members creates a cycle, i.e. a node outside of the members
    lies on a path between two members (the merged node would be before and after it).
    """
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)
    for edge in request.edges:
        successors[edge.source[0]].add(edge.target[0])
        predecessors[edge.target[0]].add(edge.source[0])
    between = _reachable(members, successors) & _reachable(members, predecessors)
    return bool(between - members)


def _topological(members: list[str], request: CompileRequest) -> list[str]:
    """Members in topological order (Kahn), ties keep node order."""
    member_set = set(members)
    in_degree = dict.fromkeys(members, 0)
    successors: dict[str, list[str]] = defaultdict(list)
    for edge in request.edges:
        source, target = edge.source[0], edge.target[0]
        if source in member_set and target in member_set and source != target:
            successors[source].append(target)
            in_degree[target] += 1
    queue = deque(node_id for node_id in members if in_degree[node_id] == 0)
    order = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for successor in successors[node_id]:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)
    order.extend(node_id for node_id in members if node_id not in order)
    return order


def _merged_node(nodes: list[ImplementationNode]) -> ImplementationNode:
    labels = [node.label or node.id for node in nodes]
    requirements = merge_requirements(
        "\n".join(node.requirements or "" for node in nodes), []
    )
    # as .env lines, invalid lines are reported when the service is generated
    environment = "\n".join(
        "\n".join(f"{name}={value}" for name, value in node.environment.items())
        if isinstance(node.environment, dict)
        else node.environment
        for node in nodes
        if node.environment
    )
    return ImplementationNode(
        id=nodes[0].id,
        label=" + ".join(labels),
        language="python",
        implementation="\n".join(
            f"# @part {label}\n{node.implementation.rstrip()}\n"
            for label, node in zip(labels, nodes, strict=True)
        ),
        requirements="\n".join(dict.fromkeys(requirements)) or None,
        environment=environment or None,
    )


def _remap_index(names: list[str], index: int, merged_names: list[str]) -> int | None:
    """
    Index of the variable at ``names[index]`` in ``merged_names``,
    None if it is no longer part of them (variable passed inside the merged node).
    """
    if index >= len(names):
        return index
    if names[index] not in merged_names:
        return None
    return merged_names.index(names[index])


def merge_object_blocks(request: CompileRequest) -> CompileRequest:
    """
    Merge the python nodes that pass objects to each other into one python node.

    The merged node gets the id of its first block (in topological order). Edges
    between the merged blocks are dropped, the other edges are redirected to the
    merged node with the index of the variable in its interface.
    Groups whose merge would create a cycle (another node between two blocks) are
    not merged; their objects are then pickled by the services.

    :return: The request with merged nodes, or the request itself if nothing is merged.
    """
    python_nodes = {
        node.id: node for node in request.nodes if is_python_implementation(node)
    }
    if len(python_nodes) < 2:  # noqa: PLR2004
        return request
    try:
        interfaces = {
            node_id: parse_python_implementation(node.implementation).interface
            for node_id, node in python_nodes.items()
        }
    except PythonAnnotationError:
        return request  # reported when the services are generated

    groups = [
        _topological(members, request)
        for members in _groups(
            list(python_nodes), _object_edges(request, python_nodes, interfaces)
        )
    ]
    groups = [
        members for members in groups if not _creates_cycle(set(members), request)
    ]
    if not groups:
        return request

    merged_id: dict[str, str] = {}
    merged_nodes: dict[str, ImplementationNode] = {}
    merged_interfaces: dict[str, PythonServiceInterface] = {}
    for members in groups:
        merged = _merged_node([python_nodes[node_id] for node_id in members])
        merged_nodes[merged.id] = merged
        merged_interfaces[merged.id] = parse_python_implementation(
            merged.implementation
        ).interface
        for node_id in members:
            merged_id[node_id] = merged.id

    nodes = []
    for node in request.nodes:
        if node.id not in merged_id:
            nodes.append(node)
        elif merged_id[node.id] == node.id:
            nodes.append(merged_nodes[node.id])

    edges: list[Edge] = []
    for edge in request.edges:
        (source, source_index), (target, target_index) = edge.source, edge.target
        new_source, new_target = merged_id.get(source), merged_id.get(target)
        if new_source is not None and new_source == new_target:
            continue  # passed inside the merged node
        if new_source is not None:
            index = _remap_index(
                interfaces[source].outputs,
                source_index,
                merged_interfaces[new_source].outputs,
            )
            source, source_index = new_source, source_index if index is None else index
        if new_target is not None:
            index = _remap_index(
                interfaces[target].inputs,
                target_index,
                merged_interfaces[new_target].inputs,
            )
            if index is None:
                continue  # the input is produced inside the merged node
            target, target_index = new_target, index
        edges.append(
            edge.model_copy(
                update={
                    "source": (source, source_index),
                    "target": (target, target_index),
                }
            )
        )

    print(
        "merged python nodes that pass objects:",
        {
            merged: [m for m, g in merged_id.items() if g == merged]
            for merged in merged_nodes
        },
    )
    return request.model_copy(update={"nodes": nodes, "edges": edges})
