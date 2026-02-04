from __future__ import annotations
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from typing import Any, Tuple, Optional
from app.transformation_manager import bpmn_templates as GroovyScript

# BPMN namespaces
BPMN2_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
CAMUNDA_NS = "http://camunda.org/schema/1.0/bpmn"
QUANTME_NS = "https://github.com/UST-QuAntiL/QuantME-Quantum4BPMN"
OpenTOSCA_NS = "https://github.com/UST-QuAntiL/OpenTOSCA"

# Layout Configuration
BPMN_START_X = 252
BPMN_START_Y = 222
BPMN_TASK_WIDTH = 120
BPMN_TASK_HEIGHT = 80
BPMN_GAP_X = 220
BPMN_GAP_Y = 150
BPMN_CHAIN_X_OFFSET = 170
BPMN_CHAIN_Y_BASE = 200
BPMN_EVENT_WIDTH = 36
BPMN_EVENT_HEIGHT = 36
BPMN_GW_WIDTH = 50
BPMN_GW_HEIGHT = 50
BPMN_FLOW_ID_LENGTH = 7


class BpmnBuilder:
    def __init__(
        self,
        process_id: str,
        nodes: dict[str, Any],
        edges: list[tuple[str, str]],
        metadata: dict[str, Any] | None = None,
        start_event_classical_nodes: list[Any] | None = None,
        containsPlaceholder: bool = False,
    ):
        """
        Initializes the BpmnBuilder.

        Args:
            process_id: Unique identifier for the process.
            nodes: Dictionary of program nodes.
            edges: List of edges (source, target).
            metadata: Process metadata.
            start_event_classical_nodes: List of classical nodes to be inputs on Start Event.
            containsPlaceholder: Whether to generate the placeholder workflow structure.
        """
        self.process_id = process_id
        self.nodes = nodes
        self.edges = edges
        self.metadata = metadata or {}
        self.start_event_classical_nodes = start_event_classical_nodes or []
        self.containsPlaceholder = containsPlaceholder

        self._register_namespaces()
        self._init_xml()

        self.start_id = "StartEvent_1"
        self.end_id = "EndEvent_1"
        self.gateway_default_targets = {}
        self.task_positions = {}
        self.inserted_chains = {}
        self.human_tasks = {}
        self.fail_job_tasks = {}
        self.fail_transf_tasks = {}
        self.update_tasks = {}
        self.alt_ends = defaultdict(list)
        self.alt_end_event_ids = set()

    def _register_namespaces(self) -> None:
        """Registers XML namespaces used in BPMN generation."""
        ET.register_namespace("bpmn", BPMN2_NS)
        ET.register_namespace("bpmndi", BPMNDI_NS)
        ET.register_namespace("dc", DC_NS)
        ET.register_namespace("di", DI_NS)
        ET.register_namespace("camunda", CAMUNDA_NS)
        ET.register_namespace("xsi", XSI_NS)

    def _init_xml(self) -> None:
        """Initializes the base XML structure (definitions and process)."""
        self.defs = ET.Element(
            self.qn(BPMN2_NS, "definitions"),
            {
                "id": "sample-diagram",
                "targetNamespace": "http://bpmn.io/schema/bpmn",
                self.qn(
                    XSI_NS, "schemaLocation"
                ): "http://www.omg.org/spec/BPMN/20100524/MODEL BPMN20.xsd",
            },
        )
        self.process = ET.SubElement(
            self.defs,
            self.qn(BPMN2_NS, "process"),
            {"id": f"Process_{self.process_id}", "isExecutable": "true"},
        )

    def qn(self, ns: str, tag: str) -> str:
        """Returns the qualified name string {namespace}tag."""
        return f"{{{ns}}}{tag}"

    def new_flow(self) -> str:
        """Generates a unique ID for a sequence flow."""
        return f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"

    def build(self) -> tuple[str, list[str]]:
        """
        Builds the complete BPMN XML and returns it along with the list of created tasks.

        Returns:
            A tuple containing the XML string and a list of all activity IDs.
        """

        self._create_start_event()
        self._create_end_event()

        # Analyze Structure
        incoming, outgoing = self._analyze_graph()
        start_nodes = [nid for nid in self.nodes.keys() if not incoming[nid]]

        # Create Chains
        for start_node in start_nodes:
            if self.containsPlaceholder:
                self._create_chain_placeholder(start_node)
            else:
                self._create_chain_standard(start_node)

        # Layout
        self._calculate_layout(start_nodes, incoming, outgoing)

        # Connect Flows
        self._connect_flows(start_nodes)

        # Diagram
        self._create_diagram(start_nodes)

        all_activities = list(self.nodes.keys())
        for start_node, chain in self.inserted_chains.items():
            all_activities.extend(chain)
            all_activities += [
                self.human_tasks[start_node],
                self.fail_job_tasks[start_node],
                self.alt_ends[start_node][-1],
            ]
            if self.containsPlaceholder:
                all_activities += [
                    self.update_tasks[start_node],
                    self.fail_transf_tasks[start_node],
                    self.alt_ends[start_node][0],
                ]

        return ET.tostring(self.defs, encoding="unicode"), all_activities

    def _create_start_event(self) -> None:
        """Creates the Start Event and configures its form fields."""
        start_event = ET.SubElement(
            self.process, self.qn(BPMN2_NS, "startEvent"), {"id": self.start_id}
        )
        ext = ET.SubElement(start_event, self.qn(BPMN2_NS, "extensionElements"))
        form = ET.SubElement(ext, self.qn(CAMUNDA_NS, "formData"))
        ET.SubElement(
            form,
            self.qn(CAMUNDA_NS, "formField"),
            {
                "id": "ipAdress",
                "label": "IP Adresse",
                "type": "string",
                "defaultValue": "192.168.178.65",
            },
        )

        if self.start_event_classical_nodes:
            for node in self.start_event_classical_nodes:
                node_id = getattr(node, "id", None) or "unknown"
                node_label = getattr(node, "label", None) or node_id
                ET.SubElement(
                    form,
                    self.qn(CAMUNDA_NS, "formField"),
                    {
                        "id": f"Input_{node_id.replace('-', '_')}_value",
                        "label": node_label,
                        "type": "string",
                        "defaultValue": "0",
                    },
                )

    def _create_end_event(self) -> None:
        """Creates the End Event."""
        ET.SubElement(self.process, self.qn(BPMN2_NS, "endEvent"), {"id": self.end_id})

    def _analyze_graph(self) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Analyzes the graph to build adjacency maps."""
        incoming, outgoing = defaultdict(list), defaultdict(list)
        for src, tgt in self.edges:
            outgoing[src].append(tgt)
            incoming[tgt].append(src)
        return incoming, outgoing

    def _create_exclusive_gateway(self, gateway_id: str) -> None:
        """Creates an Exclusive Gateway element."""
        attrs = {"id": gateway_id}
        if gateway_id in self.gateway_default_targets:
            attrs["default"] = self.gateway_default_targets[gateway_id]
        ET.SubElement(self.process, self.qn(BPMN2_NS, "exclusiveGateway"), attrs)

    def _place_gateway_between(self, left_id: str, right_id: str, gateway_id: str):
        lx, ly = self.task_positions[left_id]
        rx, _ = self.task_positions[right_id]

        gx = (
            lx
            + BPMN_TASK_WIDTH
            + ((rx - (lx + BPMN_TASK_WIDTH)) // 2)
            - BPMN_GW_WIDTH // 2
        )
        gy = ly + BPMN_TASK_HEIGHT // 2 - BPMN_GW_HEIGHT // 2

        self.task_positions[gateway_id] = (gx, gy)

    def _create_service_task(
        self,
        task_id: str,
        name: str,
        connector_payload_script: str | None = None,
        connector_output_var: str | None = None,
        connector_output_script: str | None = None,
        extra_inputs: dict[str, str] | None = None,
        extra_outputs: dict[str, str] | None = None,
        async_after: bool = True,
        exclusive: bool = False,
    ) -> None:
        """Creates a Service Task with Camunda connector configuration."""
        attrs = {"id": task_id, "name": name}
        if async_after:
            attrs[self.qn(CAMUNDA_NS, "asyncAfter")] = "true"
        if exclusive:
            attrs[self.qn(CAMUNDA_NS, "exclusive")] = (
                "true"  # usually false in code unless setCircuit
            )
        else:
            attrs[self.qn(CAMUNDA_NS, "exclusive")] = "false"

        task = ET.SubElement(self.process, self.qn(BPMN2_NS, "serviceTask"), attrs)

        if connector_payload_script or extra_inputs or extra_outputs:
            ext = ET.SubElement(task, self.qn(BPMN2_NS, "extensionElements"))
            connector = ET.SubElement(ext, self.qn(CAMUNDA_NS, "connector"))
            ET.SubElement(
                connector, self.qn(CAMUNDA_NS, "connectorId")
            ).text = "http-connector"
            io = ET.SubElement(connector, self.qn(CAMUNDA_NS, "inputOutput"))

            # Common headers
            headers = ET.SubElement(
                io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "headers"}
            )
            header_map = ET.SubElement(headers, self.qn(CAMUNDA_NS, "map"))
            ET.SubElement(
                header_map, self.qn(CAMUNDA_NS, "entry"), {"key": "Accept"}
            ).text = "application/json"
            ET.SubElement(
                header_map, self.qn(CAMUNDA_NS, "entry"), {"key": "Content-Type"}
            ).text = "application/json"

            if extra_inputs:
                for k, v in extra_inputs.items():
                    ET.SubElement(
                        io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": k}
                    ).text = v

            if connector_payload_script:
                payload_param = ET.SubElement(
                    io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "payload"}
                )
                script = ET.SubElement(
                    payload_param,
                    self.qn(CAMUNDA_NS, "script"),
                    {"scriptFormat": "groovy"},
                )
                script.text = connector_payload_script

            if connector_output_var and connector_output_script:
                out_param = ET.SubElement(
                    io,
                    self.qn(CAMUNDA_NS, "outputParameter"),
                    {"name": connector_output_var},
                )
                script = ET.SubElement(
                    out_param, self.qn(CAMUNDA_NS, "script"), {"scriptFormat": "groovy"}
                )
                script.text = connector_output_script

            if extra_outputs:
                for k, v in extra_outputs.items():
                    out_param = ET.SubElement(
                        io, self.qn(CAMUNDA_NS, "outputParameter"), {"name": k}
                    )
                    script = ET.SubElement(
                        out_param,
                        self.qn(CAMUNDA_NS, "script"),
                        {"scriptFormat": "groovy"},
                    )
                    script.text = v

    def _create_script_task(
        self,
        task_id: str,
        name: str,
        script_content: str,
        async_after: bool = False,
        exclusive: bool = False,
    ) -> None:
        """Creates a Script Task with Groovy script content."""
        attrs = {"id": task_id, "name": name, "scriptFormat": "groovy"}
        if async_after:
            attrs[self.qn(CAMUNDA_NS, "asyncAfter")] = "true"
        if exclusive:
            attrs[self.qn(CAMUNDA_NS, "exclusive")] = "true"

        task = ET.SubElement(self.process, self.qn(BPMN2_NS, "scriptTask"), attrs)
        ET.SubElement(task, self.qn(BPMN2_NS, "script")).text = script_content

    def _create_chain_common(
        self, start_node: str
    ) -> tuple[str, str, str, str, str, str]:
        """Creates the common sub-process chain (Deployment -> Execute -> Res -> Gateway)."""
        # IDs
        createdeploym_id = f"Task_{start_node}_create_deployment"
        exejob_id = f"Task_{start_node}_exe_job"
        getjobres_id = f"Task_{start_node}_get_job_res"
        setvars2_id = f"Task_{start_node}_set_vars_2"
        analyzefailedjob_id = f"Task_{start_node}_analyze_failed_job"
        gateway3_id = f"Task_{start_node}_gateway_3"
        gateway4_id = f"Task_{start_node}_gateway_4"
        human_task_id = f"Task_{start_node}_human"
        altend2_id = f"Task_{start_node}_alt_end_2"

        # Save IDs
        self.human_tasks[start_node] = human_task_id
        self.fail_job_tasks[start_node] = analyzefailedjob_id
        self.alt_ends[start_node].append(altend2_id)
        self.alt_end_event_ids.add(altend2_id)

        # Elements
        self._create_service_task(
            createdeploym_id,
            "Create Deployment",
            GroovyScript.PAYLOAD_CREATE_DEPLOYMENT,
            "deploymentId",
            GroovyScript.OUTPUT_DEPLOYMENT_ID,
            extra_inputs={
                "method": "POST",
                "url": "http://${ipAdress}:8080/deployments/",
            },
        )

        self._create_service_task(
            exejob_id,
            "Execute Job",
            GroovyScript.PAYLOAD_EXECUTE_JOB,
            "jobId",
            GroovyScript.OUTPUT_JOB_ID,
            extra_inputs={"method": "POST", "url": "http://${ipAdress}:8080/jobs/"},
        )

        self._create_service_task(
            getjobres_id,
            "Get Job Results",
            extra_inputs={"method": "GET", "url": "http://${ipAdress}:8080${jobId}"},
            extra_outputs={
                "resultExecution": GroovyScript.OUTPUT_RESULT_EXECUTION,
                "statusJob": GroovyScript.OUTPUT_STATUS_JOB,
            },
            async_after=False,
            exclusive=False,
        )  # Defaults in orig code? Check below... orig code didn't specify async on getjobres, so False.

        self._create_script_task(
            setvars2_id, "Set Variables", GroovyScript.SCRIPT_SET_VARS_2
        )

        ET.SubElement(
            self.process,
            self.qn(BPMN2_NS, "userTask"),
            {"id": human_task_id, "name": "Analyze Results"},
        )
        self._create_exclusive_gateway(
            gateway3_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute
        self._create_exclusive_gateway(
            gateway4_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute

        ET.SubElement(
            self.process,
            self.qn(BPMN2_NS, "userTask"),
            {"id": analyzefailedjob_id, "name": "Analyze Failed Job"},
        )
        ET.SubElement(
            self.process, self.qn(BPMN2_NS, "endEvent"), {"id": altend2_id, "name": ""}
        )

        return (
            createdeploym_id,
            exejob_id,
            getjobres_id,
            setvars2_id,
            gateway3_id,
            gateway4_id,
        )

    def _create_chain_standard(self, start_node: str) -> None:
        """Creates the standard execution chain (SetCircuit -> Common)."""
        setcirc_id = f"Task_{start_node}_set_circuit"

        # Common parts
        (
            createdeploym_id,
            exejob_id,
            getjobres_id,
            setvars2_id,
            gateway3_id,
            gateway4_id,
        ) = self._create_chain_common(start_node)

        # Specific parts
        self._create_script_task(
            setcirc_id,
            "Set Circuit",
            GroovyScript.SCRIPT_SET_CIRCUIT,
            async_after=True,
            exclusive=True,
        )

        self.inserted_chains[start_node] = (
            setcirc_id,
            createdeploym_id,
            exejob_id,
            gateway3_id,
            getjobres_id,
            gateway4_id,
            setvars2_id,
        )

    def _create_chain_placeholder(self, start_node: str) -> None:
        """Creates the placeholder execution chain (BackendReq -> Poll -> Retrieve -> Common)."""
        setvars1_id = f"Task_{start_node}_set_vars_1"
        backendreq_id = f"Task_{start_node}_backend_req"
        pollstat_id = f"Task_{start_node}_poll_status"
        retrievecirc_id = f"Task_{start_node}_retrieve_circuit"
        updatevars_id = f"Task_{start_node}_update_vars"
        analyzefailedtransf_id = f"Task_{start_node}_analyze_failed_transf"
        gateway1_id = f"Task_{start_node}_gateway_1"
        gateway2_id = f"Task_{start_node}_gateway_2"
        altend1_id = f"Task_{start_node}_alt_end_1"

        self.update_tasks[start_node] = updatevars_id
        self.fail_transf_tasks[start_node] = analyzefailedtransf_id
        self.alt_ends[start_node].insert(0, altend1_id)
        self.alt_end_event_ids.add(altend1_id)

        # Common parts
        (
            createdeploym_id,
            exejob_id,
            getjobres_id,
            setvars2_id,
            gateway3_id,
            gateway4_id,
        ) = self._create_chain_common(start_node)

        # Specific parts
        self._create_script_task(
            setvars1_id, "Set Variables", GroovyScript.SCRIPT_SET_VARS_1
        )

        self._create_service_task(
            backendreq_id,
            "Send Backend Request",
            GroovyScript.PAYLOAD_BACKEND_REQ,
            "uuid",
            GroovyScript.OUTPUT_UUID,
            extra_inputs={"method": "POST", "url": "http://${ipAdress}:8000/compile"},
        )

        self._create_service_task(
            pollstat_id,
            "Poll Status",
            extra_inputs={
                "method": "GET",
                "url": "http://${ipAdress}:8000/status/${uuid}",
            },
            extra_outputs={"status": GroovyScript.OUTPUT_STATUS},
        )

        self._create_service_task(
            retrievecirc_id,
            "Retrieve Circuit",
            extra_inputs={
                "method": "GET",
                "url": "http://${ipAdress}:8000/results/${uuid}",
            },
            extra_outputs={"circuit": GroovyScript.OUTPUT_CIRCUIT},
            async_after=False,
            exclusive=False,
        )  # check defaults

        self._create_exclusive_gateway(
            gateway1_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute
        self._create_exclusive_gateway(
            gateway2_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute

        self._create_script_task(
            updatevars_id, "Update Variables", GroovyScript.SCRIPT_UPDATE_VARS
        )
        ET.SubElement(
            self.process,
            self.qn(BPMN2_NS, "userTask"),
            {"id": analyzefailedtransf_id, "name": "Analyze Failed Transformation"},
        )
        ET.SubElement(
            self.process, self.qn(BPMN2_NS, "endEvent"), {"id": altend1_id, "name": ""}
        )

        self.inserted_chains[start_node] = (
            setvars1_id,
            backendreq_id,
            gateway1_id,
            pollstat_id,
            gateway2_id,
            retrievecirc_id,
            createdeploym_id,
            exejob_id,
            gateway3_id,
            getjobres_id,
            gateway4_id,
            setvars2_id,
        )

    def _calculate_layout(
        self,
        start_nodes: list[str],
        incoming: dict[str, list[str]],
        outgoing: dict[str, list[str]],
    ) -> None:
        """Calculates positions for all elements in the diagram."""
        # Topological Sort & Leveling
        node_ids = list(self.nodes.keys())
        node_level = {}
        for nid in node_ids:
            if nid in start_nodes:
                node_level[nid] = 1 if self.containsPlaceholder else 0

        # Topological sort
        indegree = {nid: len(incoming[nid]) for nid in node_ids}
        queue = deque(start_nodes)
        topo_order = []
        while queue:
            nid = queue.popleft()
            topo_order.append(nid)
            for tgt in outgoing[nid]:
                indegree[tgt] -= 1
                if indegree[tgt] == 0:
                    queue.append(tgt)
        for nid in node_ids:
            if nid not in topo_order:
                topo_order.append(nid)

        # compute levels by topo_order, using incoming predecessors' levels
        level_positions = defaultdict(list)
        for nid in topo_order:
            if nid not in node_level:
                predecessors = incoming[nid]
                if predecessors:
                    node_level[nid] = (
                        max(node_level.get(p, 0) for p in predecessors) + 1
                    )
                else:
                    node_level[nid] = 1
            level_positions[node_level[nid]].append(nid)

        # place chain tasks at level 0; if multiple start nodes, they'll be stacked vertically
        for chain_level, start_node in enumerate(start_nodes):
            x = BPMN_START_X + BPMN_CHAIN_X_OFFSET
            y = BPMN_CHAIN_Y_BASE + chain_level * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)

            chain = self.inserted_chains[start_node]
            human_id = self.human_tasks[start_node]

            # Common tail always present
            tail = chain[-6:]
            (
                createdeploym_id,
                exejob_id,
                gateway3_id,
                getjobres_id,
                gateway4_id,
                setvars2_id,
            ) = tail

            # place common tasks
            self.task_positions[createdeploym_id] = (
                x + 4 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                y,
            )
            self.task_positions[exejob_id] = (x + 5 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
            self.task_positions[getjobres_id] = (
                x + 6 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                y,
            )

            # Gateway 3
            self._place_gateway_between(exejob_id, getjobres_id, gateway3_id)
            self.task_positions[setvars2_id] = (
                x + 7 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                y,
            )

            # Gateway 4
            self._place_gateway_between(getjobres_id, setvars2_id, gateway4_id)
            self.task_positions[human_id] = (x + 8 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)

            analyzefailedjob_id = self.fail_job_tasks[start_node]
            # place transformation tasks
            if self.containsPlaceholder:
                (
                    setvars1_id,
                    backendreq_id,
                    gateway1_id,
                    pollstat_id,
                    gateway2_id,
                    retrievecirc_id,
                    *_,
                ) = chain

                updatevars_id = self.update_tasks[start_node]
                analyzefailedtransf_id = self.fail_transf_tasks[start_node]

                self.task_positions[setvars1_id] = (x, y)
                self.task_positions[backendreq_id] = (
                    x + 1 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y,
                )
                self.task_positions[pollstat_id] = (
                    x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y,
                )

                # Gateway 1
                self._place_gateway_between(backendreq_id, pollstat_id, gateway1_id)
                self.task_positions[retrievecirc_id] = (
                    x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y,
                )

                # Gateway 2
                self._place_gateway_between(pollstat_id, retrievecirc_id, gateway2_id)
                self.task_positions[updatevars_id] = (
                    x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y - BPMN_TASK_HEIGHT - 30,
                )

                gx2, gy2 = self.task_positions[gateway2_id]
                self.task_positions[analyzefailedtransf_id] = (
                    gx2,
                    gy2 + BPMN_TASK_HEIGHT + 20,
                )
                self.task_positions[analyzefailedjob_id] = (
                    x + 7 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y + BPMN_TASK_HEIGHT + 30,
                )

            else:
                # no placeholder part
                setcirc_id = chain[0]
                self.task_positions[setcirc_id] = (x, y)
                self.task_positions[analyzefailedjob_id] = (
                    x + 7 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    y + BPMN_TASK_HEIGHT + 30,
                )

            # alternative end events
            afj_x, afj_y = self.task_positions[analyzefailedjob_id]
            for altend_id in self.alt_ends.get(start_node, []):
                if altend_id.endswith("_alt_end_2"):
                    self.task_positions[altend_id] = (
                        afj_x + BPMN_TASK_WIDTH + BPMN_GAP_X // 2,
                        afj_y + 28,
                    )
                else:
                    # alt_end_1
                    self.task_positions[altend_id] = (
                        x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X) + 30,
                        afj_y + 28,
                    )

        # Place original nodes
        for level, nids in level_positions.items():
            for i, nid in enumerate(nids):
                # shift x by +1 level because chain occupies level 0
                x = (
                    BPMN_START_X
                    + BPMN_CHAIN_X_OFFSET
                    + (level + 3) * (BPMN_TASK_WIDTH + BPMN_GAP_X)
                )
                y = BPMN_CHAIN_Y_BASE + i * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)
                if not nid.startswith("quantum_group_"):
                    self.task_positions[f"Task_{nid}"] = (x, y)

    def _connect_flows(self, start_nodes: list[str]) -> None:
        """Creates sequence flows connecting the chains and elements."""
        ordered_starts = start_nodes
        flow_map = []

        for i, start_node in enumerate(ordered_starts):
            chain = self.inserted_chains[start_node]
            human_id = self.human_tasks[start_node]
            altend2_id = self.alt_ends[start_node][-1]
            analyzefailedjob_id = self.fail_job_tasks[start_node]

            # unpack chain tail
            createdeploym_id = chain[-6]
            exejob_id = chain[-5]
            gateway3_id = chain[-4]
            getjobres_id = chain[-3]
            gateway4_id = chain[-2]
            setvars2_id = chain[-1]

            if self.containsPlaceholder:
                setvars1_id = chain[0]
                backendreq_id = chain[1]
                gateway1_id = chain[2]
                pollstat_id = chain[3]
                gateway2_id = chain[4]
                retrievecirc_id = chain[5]

                updatevars_id = self.update_tasks[start_node]
                analyzefailedtransf_id = self.fail_transf_tasks[start_node]
                altend1_id = self.alt_ends[start_node][0]

                if i == 0:
                    flow_map.append((self.new_flow(), self.start_id, setvars1_id))

                flow_map.append((self.new_flow(), setvars1_id, backendreq_id))

                fid = self.new_flow()
                flow_map.append((fid, gateway1_id, pollstat_id))
                self.gateway_default_targets[gateway1_id] = fid

                flow_map.append((self.new_flow(), backendreq_id, gateway1_id))
                flow_map.append((self.new_flow(), pollstat_id, gateway2_id))

                # Gateway 2
                fid_ret = self.new_flow()
                flow_map.append((fid_ret, gateway2_id, retrievecirc_id))

                fid_def = self.new_flow()
                flow_map.append((fid_def, gateway2_id, analyzefailedtransf_id))
                self.gateway_default_targets[gateway2_id] = fid_def

                flow_map.append((self.new_flow(), gateway2_id, updatevars_id))

                # Success path
                flow_map.append((self.new_flow(), retrievecirc_id, createdeploym_id))

                flow_map.append((self.new_flow(), analyzefailedtransf_id, altend1_id))
                flow_map.append((self.new_flow(), updatevars_id, gateway1_id))

            else:
                setcirc_id = chain[0]
                if i == 0:
                    flow_map.append((self.new_flow(), self.start_id, setcirc_id))
                flow_map.append((self.new_flow(), setcirc_id, createdeploym_id))

            # Common tail flows
            flow_map.append((self.new_flow(), createdeploym_id, exejob_id))
            flow_map.append((self.new_flow(), exejob_id, gateway3_id))

            fid = self.new_flow()
            flow_map.append((fid, gateway3_id, getjobres_id))
            self.gateway_default_targets[gateway3_id] = fid

            flow_map.append((self.new_flow(), getjobres_id, gateway4_id))

            fid = self.new_flow()
            flow_map.append((fid, gateway4_id, setvars2_id))
            self.gateway_default_targets[gateway4_id] = fid

            flow_map.append((self.new_flow(), setvars2_id, human_id))
            flow_map.append((self.new_flow(), gateway4_id, analyzefailedjob_id))
            flow_map.append((self.new_flow(), analyzefailedjob_id, altend2_id))
            flow_map.append((self.new_flow(), gateway4_id, gateway3_id))

            # Next or End
            if i + 1 < len(ordered_starts):
                next_chain = self.inserted_chains[ordered_starts[i + 1]]
                flow_map.append((self.new_flow(), human_id, next_chain[0]))
            else:
                flow_map.append((self.new_flow(), human_id, self.end_id))

        # Update gateway defaults in XML
        for gateway_id, default_fid in self.gateway_default_targets.items():
            gw = self.process.find(f".//*[@id='{gateway_id}']")
            if gw is not None:
                gw.set("default", default_fid)

        # Create Sequence Flows
        for fid, src, tgt in flow_map:
            self._create_sequence_flow(fid, src, tgt)

        # Store edges for Diagram
        self.flow_map = flow_map

    def _create_sequence_flow(self, fid: str, src: str, tgt: str) -> None:
        """Helper to create a single Sequence Flow element."""
        # Resolve IDs
        # src/tgt are bare IDs (e.g. StartEvent_1) or task keys (Task_X)
        src_el_id = src
        tgt_el_id = tgt

        src_el = self.process.find(f".//*[@id='{src_el_id}']")
        tgt_el = self.process.find(f".//*[@id='{tgt_el_id}']")

        if src_el is not None:
            ET.SubElement(src_el, self.qn(BPMN2_NS, "outgoing")).text = fid
        if tgt_el is not None:
            ET.SubElement(tgt_el, self.qn(BPMN2_NS, "incoming")).text = fid

        sf = ET.SubElement(
            self.process,
            self.qn(BPMN2_NS, "sequenceFlow"),
            {"id": fid, "sourceRef": src_el_id, "targetRef": tgt_el_id},
        )

        # gateway conditions
        if src in self.gateway_default_targets:
            default_fid = self.gateway_default_targets[src]
            if fid != default_fid:
                if src.endswith("_gateway_2"):
                    cond = ET.SubElement(
                        sf,
                        self.qn(BPMN2_NS, "conditionExpression"),
                        {self.qn(XSI_NS, "type"): "bpmn:tFormalExpression"},
                    )
                    if tgt.endswith("_retrieve_circuit"):
                        cond.text = '${status == "completed"}'
                    elif tgt.endswith("_update_vars"):
                        cond.text = '${status != "completed"}'
                elif src.endswith("_gateway_4"):
                    cond = ET.SubElement(
                        sf,
                        self.qn(BPMN2_NS, "conditionExpression"),
                        {self.qn(XSI_NS, "type"): "bpmn:tFormalExpression"},
                    )
                    if tgt.endswith("_analyze_failed_job"):
                        cond.text = "${jobFailed}"
                    elif tgt.endswith("_gateway_3"):
                        cond.text = "${!jobFailed && shouldRetry}"

    def _create_diagram(self, start_nodes: list[str]) -> None:
        """Generates the BPMNDI Diagram section with shapes and edges."""

        def add_shape(eid: str, x: Any, y, w, h):
            shape = ET.SubElement(
                plane,
                self.qn(BPMNDI_NS, "BPMNShape"),
                {"id": f"{eid}_di", "bpmnElement": eid},
            )
            ET.SubElement(
                shape,
                self.qn(DC_NS, "Bounds"),
                x=str(x),
                y=str(y),
                width=str(w),
                height=str(h),
            )

        diagram = ET.SubElement(
            self.defs, self.qn(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"}
        )
        plane = ET.SubElement(
            diagram,
            self.qn(BPMNDI_NS, "BPMNPlane"),
            {"id": "BPMNPlane_1", "bpmnElement": f"Process_{self.process_id}"},
        )

        # Start shape
        add_shape(
            self.start_id,
            BPMN_START_X,
            BPMN_START_Y,
            BPMN_EVENT_WIDTH,
            BPMN_EVENT_HEIGHT,
        )

        # collect all real BPMN element ids (Tasks, Gateways, Events)
        valid_bpmn_ids = {el.attrib["id"] for el in self.process.findall(".//*[@id]")}

        # End Event X/Y - calculated based on last task
        # Find max X task
        last_x, last_y = BPMN_START_X, BPMN_START_Y
        if self.task_positions:
            last_task_id = max(self.task_positions.items(), key=lambda kv: kv[1][0])[0]
            last_x, last_y = self.task_positions[last_task_id]

        end_x = last_x + BPMN_TASK_WIDTH + BPMN_GAP_X
        end_y = last_y + (BPMN_TASK_HEIGHT // 2) - 18
        add_shape(self.end_id, end_x, end_y, BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT)

        for eid, (x, y) in self.task_positions.items():
            if eid not in valid_bpmn_ids:
                continue

            if "_gateway_" in eid:
                add_shape(eid, x, y, BPMN_GW_WIDTH, BPMN_GW_HEIGHT)
            elif eid in self.alt_end_event_ids:
                add_shape(eid, x, y, BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT)
            else:
                add_shape(eid, x, y, BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT)

        # Edges
        # Docking logic simplified for readability
        top_dock_sources = set()
        bottom_dock_sources = set()
        top_dock_targets = set()
        left_dock_sources = set()
        right_dock_targets = set()

        if self.containsPlaceholder:
            for start_node, chain in self.inserted_chains.items():
                # Reconstruct specific IDs from chain
                gateway2_id = chain[4]
                gateway3_id = chain[8]
                gateway4_id = chain[10]
                gateway1_id = chain[2]
                updatevars_id = self.update_tasks[start_node]
                analyzefailedtransf_id = self.fail_transf_tasks[start_node]
                analyzefailedjob_id = self.fail_job_tasks[start_node]

                top_dock_sources.add((gateway2_id, updatevars_id))
                bottom_dock_sources.add((gateway2_id, analyzefailedtransf_id))
                bottom_dock_sources.add((gateway4_id, analyzefailedjob_id))
                top_dock_sources.add((gateway4_id, gateway3_id))

                top_dock_targets.add((updatevars_id, gateway1_id))
                top_dock_targets.add((gateway2_id, analyzefailedtransf_id))
                top_dock_targets.add((gateway4_id, gateway3_id))

                right_dock_targets.add((gateway2_id, updatevars_id))
                left_dock_sources.add((updatevars_id, gateway1_id))
        else:
            for start_node, chain in self.inserted_chains.items():
                gateway3_id = chain[3]
                gateway4_id = chain[5]
                analyzefailedjob_id = self.fail_job_tasks[start_node]

                bottom_dock_sources.add((gateway4_id, analyzefailedjob_id))
                top_dock_sources.add((gateway4_id, gateway3_id))
                top_dock_targets.add((gateway4_id, gateway3_id))

        def get_center(eid: str, mode: str) -> tuple[int, int]:
            x, y = self.task_positions.get(eid, (0, 0))
            w, h = BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT
            if "_gateway_" in eid:
                w, h = BPMN_GW_WIDTH, BPMN_GW_HEIGHT
            # Start/End events handled separately usually?
            # But flow map has start_id/end_id
            if eid == self.start_id:
                x, y, w, h = (
                    BPMN_START_X,
                    BPMN_START_Y,
                    BPMN_EVENT_WIDTH,
                    BPMN_EVENT_HEIGHT,
                )
            elif eid == self.end_id:
                x, y, w, h = end_x, end_y, BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT
            elif eid in self.alt_end_event_ids:
                w, h = BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT

            if mode == "bottom":
                return x + w // 2, y + h
            if mode == "top":
                return x + w // 2, y
            if mode == "left":
                return x, y + h // 2
            if mode == "right":
                return x + w, y + h // 2
            return x + w, y + h // 2  # default right

        for fid, src, tgt in self.flow_map:
            edge = ET.SubElement(
                plane,
                self.qn(BPMNDI_NS, "BPMNEdge"),
                {"id": f"{fid}_di", "bpmnElement": fid},
            )

            # Source
            mode = "right"
            if (src, tgt) in bottom_dock_sources:
                mode = "bottom"
            elif (src, tgt) in top_dock_sources:
                mode = "top"
            elif (src, tgt) in left_dock_sources:
                mode = "left"

            sx, sy = get_center(src, mode)

            # Target
            mode = "left"
            if (src, tgt) in top_dock_targets:
                mode = "top"
            elif (src, tgt) in right_dock_targets:
                mode = "right"

            tx, ty = get_center(tgt, mode)

            ET.SubElement(
                edge, self.qn(DI_NS, "waypoint"), x=str(int(sx)), y=str(int(sy))
            )
            if "_gateway_" in src and "_gateway_" in tgt:
                ET.SubElement(
                    edge,
                    self.qn(DI_NS, "waypoint"),
                    x=str(int(sx)),
                    y=str(int(sy) - 35),
                )
                ET.SubElement(
                    edge,
                    self.qn(DI_NS, "waypoint"),
                    x=str(int(tx)),
                    y=str(int(ty) - 35),
                )

            ET.SubElement(
                edge, self.qn(DI_NS, "waypoint"), x=str(int(tx)), y=str(int(ty))
            )
