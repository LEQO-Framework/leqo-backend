from __future__ import annotations
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from typing import Any, Tuple, Optional
from app.transformation_manager import bpmn_templates as GroovyScript
from app.model.CompileRequest import CompileRequest
import json

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
BPMN_GAP_X = 100
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
        original_request: CompileRequest | None = None,
        qasm: str | None = None,
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
            original_request: Original compile request of the model.
            qasm: The finished qasm string, if it already exists.
        """
        self.original_request = original_request
        self.model_json = json.dumps(self.original_request.model_dump())

        self.process_id = process_id
        self.nodes = nodes
        self.edges = edges
        self.metadata = metadata or {}
        self.start_event_classical_nodes = start_event_classical_nodes or []
        self.containsPlaceholder = containsPlaceholder
        self.containsPlugin = False
        self.qasm_str = qasm

        self.chain_level = 0
        self.chain_heads = []
        self.chain_ends = []

        self._register_namespaces()
        self._init_xml()

        self.start_id = "StartEvent_1"
        self.end_id = "EndEvent_1"
        self.task_positions = {}
        self.inserted_chains = {}
        self.human_tasks = {}
        self.fail_job_tasks = {}
        self.fail_transf_tasks = {}
        self.update_tasks = {}
        self.alt_ends = defaultdict(list)
        self.alt_end_event_ids = set()
        self.placeholder_values = {}

        self.task_positions_per_node = {}
        self.flow_map_per_node = {}
        self.diagram_info_per_node = {}

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
                "id": f"Definitions_{uuid.uuid4().hex[:8]}",
                "targetNamespace": "http://bpmn.io/schema/bpmn",
                "exporter": "QuantME Modeler",
                "exporterVersion": "4.5.0-nightly.20220628",
            },
        )
        self.process = ET.SubElement(
            self.defs,
            self.qn(BPMN2_NS, "process"),
            {
                "id": f"Process_{self.process_id}",
                "isExecutable": "true",
                self.qn(CAMUNDA_NS, "historyTimeToLive"): "360000",
            },
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
        print(self.model_json)
        self.placeholder_values = self.extract_placeholder_values(self.model_json)

        self._create_start_event()
        self._create_end_event()

        # Analyze Structure
        incoming, _ = self._analyze_graph()
        start_nodes = [nid for nid in self.nodes.keys() if not incoming[nid]]

        # Create Chains
        for start_node in start_nodes:
            node = self.nodes[start_node]
            self.containsPlugin = getattr(node, "type", None) == "plugin"

            if self.containsPlugin:
                plugin_name = getattr(node, "pluginName", None)
                print("plugin is: ", plugin_name)
                print("creating plugin flow")
                self._create_plugin_flow(start_node, plugin_name)
            elif self.containsPlaceholder:
                print("creating placeholder flow")
                self._create_placeholder_flow(start_node)
            else:
                print("creating nonPlaceholder flow")
                self._create_non_placeholder_flow(start_node)

        # Connect chains if there are multiple
        self.connect_chains()

        self._create_diagram()

        all_activities = list(self.nodes.keys())
        for start_node, chain in self.inserted_chains.items():
            all_activities.extend(chain)
            for task_map in [
                self.human_tasks,
                self.fail_job_tasks,
                self.update_tasks,
                self.fail_transf_tasks,
            ]:
                task_id = task_map.get(start_node)
                if task_id:
                    all_activities.append(task_id)
            if self.alt_ends.get(start_node):
                if len(self.alt_ends[start_node]) >= 1:
                    all_activities.append(self.alt_ends[start_node][0])
                if len(self.alt_ends[start_node]) >= 2:
                    all_activities.append(self.alt_ends[start_node][-1])
        all_activities = [x for x in all_activities if x is not None]

        self.remove_invalid_incoming_outgoing(self.process)

        self.indent(self.defs)
        return ET.tostring(self.defs, encoding="unicode"), all_activities

    def indent(self, elem, level=0):
        """
        Adds indentations to the ElementTree-XML-Object for a pretty print.
        """
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                self.indent(child, level + 1)
                if not child.tail or not child.tail.strip():
                    child.tail = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def remove_invalid_incoming_outgoing(self, process):
        for el in process.findall(".//*[@id]"):
            tag = el.tag
            # just extract the last part
            if tag.endswith("startEvent"):
                for c in list(el):
                    if c.tag.endswith("incoming"):
                        el.remove(c)
            if tag.endswith("endEvent"):
                for c in list(el):
                    if c.tag.endswith("outgoing"):
                        el.remove(c)

    def _fix_incoming_outgoing_order(self, element):
        """Sort extension, then all incoming, then all outgoing, then the rest."""
        # sort all children
        ext = [c for c in list(element) if c.tag.endswith("extensionElements")]
        incomings = [c for c in list(element) if c.tag.endswith("incoming")]
        outgoings = [c for c in list(element) if c.tag.endswith("outgoing")]
        rest = [c for c in list(element) if c not in ext + incomings + outgoings]
        for c in list(element):
            element.remove(c)
        for c in ext + incomings + outgoings + rest:
            element.append(c)

    def _create_plugin_flow(
        self,
        start_node: str,
        plugin_name: str,
    ) -> None:
        """Creates a flow for plugins."""

        # generate the plugin chain
        self._create_chain_clustering(start_node, plugin_name)

        # Layout
        positions = self._calculate_plugin_layout(start_node)
        self.task_positions_per_node[start_node] = positions

        # Connect Flows
        flow_map = self._connect_plugin_flows(start_node)
        self.flow_map_per_node[start_node] = flow_map

        # Important: Set the variable back to False to enable mixed workflows
        self.containsPlugin = False

        self.chain_level += 1

    def _create_placeholder_flow(
        self,
        start_node: str,
    ) -> None:
        """
        Creates a flow for flows with placeholder. Momentarily the containsPlaceholder
        variable is globally for the whole diagram instead of per start_node.
        """

        # Generate the placeholder chain
        self._create_chain_placeholder(start_node)

        # Layout
        positions = self._calculate_placeholder_layout(start_node)
        self.task_positions_per_node[start_node] = positions

        # Connect Flows
        flow_map = self._connect_placeholder_flows(start_node)
        self.flow_map_per_node[start_node] = flow_map

        self.chain_level += 1

    def _create_non_placeholder_flow(
        self,
        start_node: str,
    ) -> None:
        """
        Creates a flow for flows without a placeholder. Momentarily the containsPlaceholder
        variable is globally for the whole diagram instead of per start_node.
        """

        # Generate the nonPlaceholder chain
        self._create_chain_standard(start_node)

        # Layout
        positions = self._calculate_standard_layout(start_node)
        self.task_positions_per_node[start_node] = positions

        # Connect Flows
        flow_map = self._connect_standard_flows(start_node)
        self.flow_map_per_node[start_node] = flow_map

        self.chain_level += 1

    def _calculate_plugin_layout(
        self,
        start_node,
    ):
        """Calculates positions for all elements in the plugin flow."""
        positions = {}
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        analyzefailedjob_id = self.fail_job_tasks[start_node]

        (
            call_plugin_id,
            gateway3_id,
            poll_job_id,
            gateway4_id,
            setvars2_id,
        ) = chain

        # Place first chain tasks at level 0; if multiple start nodes, they'll be stacked vertically
        x = BPMN_START_X + BPMN_CHAIN_X_OFFSET
        y = BPMN_CHAIN_Y_BASE + self.chain_level * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)

        # Place tasks
        positions[call_plugin_id] = (x, y)
        positions[poll_job_id] = (x + (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[setvars2_id] = (x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[human_id] = (x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[analyzefailedjob_id] = (
            x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
            y + BPMN_TASK_HEIGHT + 30,
        )

        # Gateway 3
        self._place_gateway_between(call_plugin_id, poll_job_id, gateway3_id, positions)

        # Gateway 4
        self._place_gateway_between(poll_job_id, setvars2_id, gateway4_id, positions)

        if hasattr(self, "task_positions") and gateway3_id in self.task_positions:
            positions[gateway3_id] = self.task_positions[gateway3_id]
        if hasattr(self, "task_positions") and gateway4_id in self.task_positions:
            positions[gateway4_id] = self.task_positions[gateway4_id]

        # Alternative End-Events
        afj_x, afj_y = positions[analyzefailedjob_id]
        for altend_id in self.alt_ends.get(start_node, []):
            if altend_id.endswith("_alt_end_2"):
                positions[altend_id] = (
                    afj_x + BPMN_TASK_WIDTH + BPMN_GAP_X // 2,
                    afj_y + 22,
                )
            else:
                positions[altend_id] = (
                    x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X) + 30,
                    afj_y + 22,
                )

        print("plugin layout calculated")

        return positions

    def _calculate_placeholder_layout(self, start_node: str):
        """Calculates positions for all elements in the placeholder flow."""
        positions = {}
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        analyzefailedjob_id = self.fail_job_tasks[start_node]
        analyzefailedtransf_id = self.fail_transf_tasks[start_node]
        updatevars_id = self.update_tasks[start_node]

        (
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
        ) = chain

        # Place first chain tasks at level 0; if multiple start nodes, they'll be stacked vertically
        x = BPMN_START_X + BPMN_CHAIN_X_OFFSET
        y = BPMN_CHAIN_Y_BASE + self.chain_level * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)

        # Place tasks
        positions[setvars1_id] = (x, y)
        positions[backendreq_id] = (x + (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[pollstat_id] = (x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[retrievecirc_id] = (x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[createdeploym_id] = (x + 4 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[exejob_id] = (x + 5 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[getjobres_id] = (x + 6 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[setvars2_id] = (x + 7 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[human_id] = (x + 8 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[updatevars_id] = (
            x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
            y - BPMN_TASK_HEIGHT - 30,
        )
        positions[analyzefailedjob_id] = (
            x + 7 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
            y + BPMN_TASK_HEIGHT + 30,
        )

        # Gateway 1
        self._place_gateway_between(backendreq_id, pollstat_id, gateway1_id, positions)

        # Gateway 2
        self._place_gateway_between(
            pollstat_id, retrievecirc_id, gateway2_id, positions
        )

        # Gateway 3
        self._place_gateway_between(exejob_id, getjobres_id, gateway3_id, positions)

        # Gateway 4
        self._place_gateway_between(getjobres_id, setvars2_id, gateway4_id, positions)

        gx2, _ = positions[retrievecirc_id]
        positions[analyzefailedtransf_id] = (
            gx2,
            y + BPMN_TASK_HEIGHT + 30,
        )

        if hasattr(self, "task_positions") and gateway1_id in self.task_positions:
            positions[gateway1_id] = self.task_positions[gateway1_id]
        if hasattr(self, "task_positions") and gateway2_id in self.task_positions:
            positions[gateway2_id] = self.task_positions[gateway2_id]
        if hasattr(self, "task_positions") and gateway3_id in self.task_positions:
            positions[gateway3_id] = self.task_positions[gateway3_id]
        if hasattr(self, "task_positions") and gateway4_id in self.task_positions:
            positions[gateway4_id] = self.task_positions[gateway4_id]

        # Alternative End-Events
        afj_x, afj_y = positions[analyzefailedjob_id]
        for altend_id in self.alt_ends.get(start_node, []):
            if altend_id.endswith("_alt_end_2"):
                positions[altend_id] = (
                    afj_x + BPMN_TASK_WIDTH + BPMN_GAP_X // 2,
                    afj_y + 22,
                )
            else:
                positions[altend_id] = (
                    x + 4 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
                    afj_y + 22,
                )

        print("placeholder layout calculated")

        return positions

    def _calculate_standard_layout(self, start_node: str):
        """Calculates positions for all elements in the standard flow."""
        positions = {}
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        analyzefailedjob_id = self.fail_job_tasks[start_node]

        (
            setcirc_id,
            createdeploym_id,
            exejob_id,
            gateway3_id,
            getjobres_id,
            gateway4_id,
            setvars2_id,
        ) = chain

        # Place first chain tasks at level 0; if multiple start nodes, they'll be stacked vertically
        x = BPMN_START_X + BPMN_CHAIN_X_OFFSET
        y = BPMN_CHAIN_Y_BASE + self.chain_level * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)

        # Place tasks
        positions[setcirc_id] = (x, y)
        positions[createdeploym_id] = (x + (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[exejob_id] = (x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[getjobres_id] = (x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[setvars2_id] = (x + 4 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[human_id] = (x + 5 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
        positions[analyzefailedjob_id] = (
            x + 4 * (BPMN_TASK_WIDTH + BPMN_GAP_X),
            y + BPMN_TASK_HEIGHT + 30,
        )

        # Gateway 3
        self._place_gateway_between(exejob_id, getjobres_id, gateway3_id, positions)

        # Gateway 4
        self._place_gateway_between(getjobres_id, setvars2_id, gateway4_id, positions)

        if hasattr(self, "task_positions") and gateway3_id in self.task_positions:
            positions[gateway3_id] = self.task_positions[gateway3_id]
        if hasattr(self, "task_positions") and gateway4_id in self.task_positions:
            positions[gateway4_id] = self.task_positions[gateway4_id]

        # Alternative End-Events
        afj_x, afj_y = positions[analyzefailedjob_id]
        for altend_id in self.alt_ends.get(start_node, []):
            if altend_id.endswith("_alt_end_2"):
                positions[altend_id] = (
                    afj_x + BPMN_TASK_WIDTH + BPMN_GAP_X // 2,
                    afj_y + 22,
                )
            else:
                positions[altend_id] = (
                    x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X) + 30,
                    afj_y + 22,
                )

        print("standard layout calculated")

        return positions

    def _connect_plugin_flows(self, start_node):
        """Creates a sequence flow for plugin chains. Connecting the chains will be separately."""
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        altend2_id = self.alt_ends[start_node][-1]
        analyzefailedjob_id = self.fail_job_tasks[start_node]

        (
            call_plugin_id,
            gateway3_id,
            poll_job_id,
            gateway4_id,
            setvars2_id,
        ) = chain

        self.chain_heads.append(chain[0])
        self.chain_ends.append(self.human_tasks[start_node])

        flow_map = []

        if self.chain_level == 0:
            flow_map.append((self.new_flow(), self.start_id, call_plugin_id))

        flow_map.append((self.new_flow(), call_plugin_id, gateway3_id))
        flow_map.append((self.new_flow(), gateway3_id, poll_job_id))
        flow_map.append((self.new_flow(), poll_job_id, gateway4_id))
        flow_map.append((self.new_flow(), gateway4_id, setvars2_id))
        flow_map.append((self.new_flow(), setvars2_id, human_id))
        flow_map.append((self.new_flow(), gateway4_id, analyzefailedjob_id))
        flow_map.append((self.new_flow(), analyzefailedjob_id, altend2_id))
        flow_map.append((self.new_flow(), gateway4_id, gateway3_id))

        # Create Sequence Flows
        for fid, src, tgt in flow_map:
            self._create_sequence_flow(fid, src, tgt)

        print("plugin flow: main edges connected")

        return flow_map

    def _connect_placeholder_flows(self, start_node):
        """Creates a sequence flow for plugin chains. Connecting the chains will be separately."""
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        altend1_id = self.alt_ends[start_node][0]
        altend2_id = self.alt_ends[start_node][-1]
        analyzefailedjob_id = self.fail_job_tasks[start_node]
        analyzefailedtransf_id = self.fail_transf_tasks[start_node]
        updatevars_id = self.update_tasks[start_node]

        (
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
        ) = chain

        self.chain_heads.append(chain[0])
        self.chain_ends.append(self.human_tasks[start_node])

        flow_map = []

        if self.chain_level == 0:
            flow_map.append((self.new_flow(), self.start_id, setvars1_id))

        flow_map.append((self.new_flow(), setvars1_id, backendreq_id))
        flow_map.append((self.new_flow(), backendreq_id, gateway1_id))
        flow_map.append((self.new_flow(), gateway1_id, pollstat_id))
        flow_map.append((self.new_flow(), pollstat_id, gateway2_id))
        flow_map.append((self.new_flow(), gateway2_id, retrievecirc_id))
        flow_map.append((self.new_flow(), gateway2_id, updatevars_id))
        flow_map.append((self.new_flow(), updatevars_id, gateway1_id))
        flow_map.append((self.new_flow(), retrievecirc_id, createdeploym_id))
        flow_map.append((self.new_flow(), createdeploym_id, exejob_id))
        flow_map.append((self.new_flow(), exejob_id, gateway3_id))
        flow_map.append((self.new_flow(), gateway3_id, getjobres_id))
        flow_map.append((self.new_flow(), getjobres_id, gateway4_id))
        flow_map.append((self.new_flow(), gateway4_id, setvars2_id))
        flow_map.append((self.new_flow(), setvars2_id, human_id))
        flow_map.append((self.new_flow(), gateway4_id, gateway3_id))
        flow_map.append((self.new_flow(), gateway4_id, analyzefailedjob_id))
        flow_map.append((self.new_flow(), analyzefailedjob_id, altend2_id))
        flow_map.append((self.new_flow(), gateway2_id, analyzefailedtransf_id))
        flow_map.append((self.new_flow(), analyzefailedtransf_id, altend1_id))

        # Create Sequence Flows
        for fid, src, tgt in flow_map:
            self._create_sequence_flow(fid, src, tgt)

        print("placeholder flow: main edges connected")

        return flow_map

    def _connect_standard_flows(self, start_node):
        """Creates a sequence flow for standard chains. Connecting the chains will be separately."""
        chain = self.inserted_chains[start_node]
        human_id = self.human_tasks[start_node]
        altend2_id = self.alt_ends[start_node][-1]
        analyzefailedjob_id = self.fail_job_tasks[start_node]

        (
            setcirc_id,
            createdeploym_id,
            exejob_id,
            gateway3_id,
            getjobres_id,
            gateway4_id,
            setvars2_id,
        ) = chain

        self.chain_heads.append(chain[0])
        self.chain_ends.append(self.human_tasks[start_node])

        flow_map = []

        if self.chain_level == 0:
            flow_map.append((self.new_flow(), self.start_id, setcirc_id))

        flow_map.append((self.new_flow(), setcirc_id, createdeploym_id))
        flow_map.append((self.new_flow(), createdeploym_id, exejob_id))
        flow_map.append((self.new_flow(), exejob_id, gateway3_id))
        flow_map.append((self.new_flow(), gateway3_id, getjobres_id))
        flow_map.append((self.new_flow(), getjobres_id, gateway4_id))
        flow_map.append((self.new_flow(), gateway4_id, setvars2_id))
        flow_map.append((self.new_flow(), setvars2_id, human_id))
        flow_map.append((self.new_flow(), gateway4_id, analyzefailedjob_id))
        flow_map.append((self.new_flow(), analyzefailedjob_id, altend2_id))
        flow_map.append((self.new_flow(), gateway4_id, gateway3_id))

        # Create Sequence Flows
        for fid, src, tgt in flow_map:
            self._create_sequence_flow(fid, src, tgt)

        print("standard flow: main edges connected")

        return flow_map

    def _create_diagram(self):
        """Generates the BPMNDI Diagram section with shapes and edges."""

        def add_shape(eid: str, x: int, y: int, w: int, h: int):
            shape = ET.SubElement(
                plane,
                self.qn(BPMNDI_NS, "BPMNShape"),
                {
                    "id": f"{eid}_di",
                    "bpmnElement": eid,
                    "isMarkerVisible": "true",
                },
            )
            ET.SubElement(
                shape,
                self.qn(DC_NS, "Bounds"),
                x=str(x),
                y=str(y),
                width=str(w),
                height=str(h),
            )

        def add_waypoint(edge, x: int, y: int):
            ET.SubElement(
                edge, self.qn(DI_NS, "waypoint"), x=str(int(x)), y=str(int(y))
            )

        def add_orthogonal_waypoints(
            edge,
            sx: int,
            sy: int,
            tx: int,
            ty: int,
            route: str = "hv",
            up_offset: int = 40,
            pre_target_drop: int = 12,
        ):
            """
            Adds orthogonal waypoints if needed for pretty edges
            "hv": horizontal then vertical
            "vh": vertical then horizontal
            "up-left-down": start -> up -> left/right -> down -> target
            """

            # check first if up-left-down is required
            if route == "up-left-down":
                bend_y = min(sy, ty) - up_offset
                pre_target_y = ty - pre_target_drop

                add_waypoint(edge, sx, sy)
                add_waypoint(edge, sx, bend_y)
                add_waypoint(edge, tx, bend_y)
                add_waypoint(edge, tx, pre_target_y)
                add_waypoint(edge, tx, ty)
                return

            # already straight
            if sx == tx or sy == ty:
                add_waypoint(edge, sx, sy)
                add_waypoint(edge, tx, ty)
                return

            if route == "vh":
                add_waypoint(edge, sx, sy)
                add_waypoint(edge, sx, ty)
                add_waypoint(edge, tx, ty)
                return

            # default "hv"
            add_waypoint(edge, sx, sy)
            add_waypoint(edge, tx, sy)
            add_waypoint(edge, tx, ty)

        diagram = ET.SubElement(
            self.defs, self.qn(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"}
        )
        plane = ET.SubElement(
            diagram,
            self.qn(BPMNDI_NS, "BPMNPlane"),
            {"id": "BPMNPlane_1", "bpmnElement": f"Process_{self.process_id}"},
        )

        # Put together all positions
        merged_positions = {}
        for positions in self.task_positions_per_node.values():
            merged_positions.update(positions)

        # Collect all real BPMN element ids (Tasks, Gateways, Events)
        valid_bpmn_ids = {el.attrib["id"] for el in self.process.findall(".//*[@id]")}

        # End Event X/Y - calculated based on last task
        # Find max X task
        last_x, last_y = BPMN_START_X, BPMN_START_Y
        if merged_positions:
            last_task_id = max(merged_positions.items(), key=lambda kv: kv[1][0])[0]
            last_x, last_y = merged_positions[last_task_id]
        end_x = last_x + BPMN_TASK_WIDTH + BPMN_GAP_X
        end_y = last_y + (BPMN_TASK_HEIGHT // 2) - 18

        # Start/End Shape
        add_shape(
            self.start_id,
            BPMN_START_X,
            BPMN_START_Y,
            BPMN_EVENT_WIDTH,
            BPMN_EVENT_HEIGHT,
        )
        add_shape(self.end_id, end_x, end_y, BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT)

        # Shapes for all BPMN-elements
        for eid, (x, y) in merged_positions.items():
            if eid not in valid_bpmn_ids:
                continue
            if "_gateway_" in eid:
                add_shape(eid, x, y, BPMN_GW_WIDTH, BPMN_GW_HEIGHT)
            elif eid in self.alt_end_event_ids:
                add_shape(eid, x, y, BPMN_EVENT_WIDTH, BPMN_EVENT_HEIGHT)
            else:
                add_shape(eid, x, y, BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT)

        # Gather all flows of the whole diagram
        all_flows = []
        for flow_map in self.flow_map_per_node.values():
            all_flows.extend(flow_map)
        # Cross-Chain-Flows too
        cross_chain_flows = getattr(self, "cross_chain_flows", [])
        all_flows.extend(cross_chain_flows)

        if hasattr(self, "flow_map"):
            all_flows.extend(self.flow_map)

        def get_center(eid: str, mode: str) -> tuple[int, int]:
            x, y = merged_positions.get(eid, (0, 0))
            w, h = BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT
            if "_gateway_" in eid:
                w, h = BPMN_GW_WIDTH, BPMN_GW_HEIGHT
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
            return x + w // 2, y + h // 2

        for fid, src, tgt in all_flows:
            edge = ET.SubElement(
                plane,
                self.qn(BPMNDI_NS, "BPMNEdge"),
                {"id": f"{fid}_di", "bpmnElement": fid},
            )

            # Custom-Docking
            if src.endswith("_human") and tgt.endswith("_set_circuit"):
                mode_src = "bottom"
                mode_tgt = "top"
            elif src.endswith("_human") and tgt.endswith("_set_vars_1"):
                mode_src = "bottom"
                mode_tgt = "top"
            elif src.endswith("_gateway_4") and tgt.endswith("_analyze_failed_job"):
                mode_src = "bottom"
                mode_tgt = "left"
            elif "_gateway_" in src and "_gateway_" in tgt:
                mode_src = "top"
                mode_tgt = "top"
            elif src.endswith("_gateway_2") and tgt.endswith("_update_vars"):
                mode_src = "top"
                mode_tgt = "right"
            elif src.endswith("_update_vars") and tgt.endswith("_gateway_1"):
                mode_src = "left"
                mode_tgt = "top"
            elif src.endswith("_gateway_2") and tgt.endswith("_analyze_failed_transf"):
                mode_src = "bottom"
                mode_tgt = "left"
            else:
                # Normal BPMN-order
                mode_src = "right"
                mode_tgt = "left"

            sx, sy = get_center(src, mode_src)
            tx, ty = get_center(tgt, mode_tgt)

            route = "hv"
            # Custom-Edges
            if src.endswith("_gateway_4") and tgt.endswith("_gateway_3"):
                route = "up-left-down"
            elif src.endswith("_gateway_4") and tgt.endswith("_analyze_failed_job"):
                route = "vh"
            elif src.endswith("_gateway_2") and tgt.endswith("_update_vars"):
                route = "vh"
            elif src.endswith("_gateway_2") and tgt.endswith("_analyze_failed_transf"):
                route = "vh"

            add_orthogonal_waypoints(edge, sx, sy, tx, ty, route=route)

        print("global diagram created (all flows, incl. cross-chain)")

    def connect_chains(self):
        """Connects multiple chains."""
        self.cross_chain_flows = []
        for i in range(len(self.chain_ends)):
            if i + 1 < len(self.chain_heads):
                fid = self.new_flow()
                self._create_sequence_flow(
                    fid, self.chain_ends[i], self.chain_heads[i + 1]
                )
                self.cross_chain_flows.append(
                    (fid, self.chain_ends[i], self.chain_heads[i + 1])
                )
            else:
                fid = self.new_flow()
                self._create_sequence_flow(fid, self.chain_ends[i], self.end_id)
                self.cross_chain_flows.append((fid, self.chain_ends[i], self.end_id))

        print("chains connected")

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
                "defaultValue": "",
            },
        )
        ET.SubElement(
            form,
            self.qn(CAMUNDA_NS, "formField"),
            {
                "id": "qunicornPort",
                "label": "Qunicorn Endpoint Port",
                "type": "string",
                "defaultValue": "8080",
            },
        )
        ET.SubElement(
            form,
            self.qn(CAMUNDA_NS, "formField"),
            {
                "id": "backendPort",
                "label": "Leqo-Backend Endpoint Port",
                "type": "string",
                "defaultValue": "8000",
            },
        )
        ET.SubElement(
            form,
            self.qn(CAMUNDA_NS, "formField"),
            {
                "id": "pluginPort",
                "label": "QHAna Plugin Endpoint Port",
                "type": "string",
                "defaultValue": "5005",
            },
        )

        if self.placeholder_values:
            for placeholder in self.placeholder_values:
                ET.SubElement(
                    form,
                    self.qn(CAMUNDA_NS, "formField"),
                    {
                        "id": placeholder,
                        "label": placeholder,
                        "type": "string",
                        "defaultValue": "",
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
        ET.SubElement(self.process, self.qn(BPMN2_NS, "exclusiveGateway"), attrs)

    def _place_gateway_between(
        self,
        left_id: str,
        right_id: str,
        gateway_id: str,
        positions: dict[str, tuple[int, int]],
    ):
        lx, ly = positions[left_id]
        rx, _ = positions[right_id]

        gx = (
            lx
            + BPMN_TASK_WIDTH
            + ((rx - (lx + BPMN_TASK_WIDTH)) // 2)
            - BPMN_GW_WIDTH // 2
        )
        gy = ly + BPMN_TASK_HEIGHT // 2 - BPMN_GW_HEIGHT // 2

        positions[gateway_id] = (gx, gy)

    def _create_service_task(
        self,
        task_id: str,
        name: str,
        connector_payload_script: str | None = None,
        connector_output_parameters: list = None,
        extra_inputs: dict[str, str] | None = None,
        extra_input_maps: dict[str, dict[str, str]] | None = None,
        extra_outputs: dict[str, str] | None = None,
        async_after: bool = True,
        exclusive: bool = False,
        method: str = "POST",
        url: str = None,
    ) -> None:
        """Creates a Service Task with Camunda connector configuration."""
        attrs = {"id": task_id, "name": name}
        attrs[self.qn(CAMUNDA_NS, "asyncAfter")] = "true" if async_after else "false"
        attrs[self.qn(CAMUNDA_NS, "exclusive")] = "true" if exclusive else "false"
        task = ET.SubElement(self.process, self.qn(BPMN2_NS, "serviceTask"), attrs)

        ext = ET.SubElement(task, self.qn(BPMN2_NS, "extensionElements"))
        connector = ET.SubElement(ext, self.qn(CAMUNDA_NS, "connector"))
        io = ET.SubElement(connector, self.qn(CAMUNDA_NS, "inputOutput"))

        # method
        ET.SubElement(
            io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "method"}
        ).text = method

        # header
        headers = ET.SubElement(
            io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "headers"}
        )
        header_map = ET.SubElement(headers, self.qn(CAMUNDA_NS, "map"))
        # standard entry
        header_entries = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if extra_input_maps and "headers" in extra_input_maps:
            header_entries.update(extra_input_maps["headers"])
        for k, v in header_entries.items():
            ET.SubElement(header_map, self.qn(CAMUNDA_NS, "entry"), {"key": k}).text = v

        # url
        ET.SubElement(
            io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "url"}
        ).text = url

        # extra inputs
        if extra_inputs:
            for k, v in extra_inputs.items():
                ET.SubElement(
                    io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": k}
                ).text = v

        # payload param
        if connector_payload_script:
            payload_param = ET.SubElement(
                io, self.qn(CAMUNDA_NS, "inputParameter"), {"name": "payload"}
            )
            script = ET.SubElement(
                payload_param, self.qn(CAMUNDA_NS, "script"), {"scriptFormat": "groovy"}
            )
            script.text = connector_payload_script

        # output
        for param in connector_output_parameters:
            out_param = ET.SubElement(
                io, self.qn(CAMUNDA_NS, "outputParameter"), {"name": param["name"]}
            )
            script = ET.SubElement(
                out_param,
                self.qn(CAMUNDA_NS, "script"),
                {"scriptFormat": param.get("scriptFormat", "groovy")},
            )
            script.text = param["script"]

        # extra output params
        if extra_outputs:
            for k, v in extra_outputs.items():
                out_param = ET.SubElement(
                    io, self.qn(CAMUNDA_NS, "outputParameter"), {"name": k}
                )
                script = ET.SubElement(
                    out_param, self.qn(CAMUNDA_NS, "script"), {"scriptFormat": "groovy"}
                )
                script.text = v

        ET.SubElement(
            connector, self.qn(CAMUNDA_NS, "connectorId")
        ).text = "http-connector"

    def _create_script_task(
        self,
        task_id: str,
        name: str,
        script_content: str,
        async_after: bool = False,
        exclusive: bool = False,
        result_variable: str = None,
        connector: bool = False,
        connector_id: str = "http-connector",
        connector_input_parameters: list = None,
        connector_output_parameters: list = None,
    ) -> None:
        """Creates a Script Task with Groovy script content and option for camunda connector"""
        attrs = {"id": task_id, "name": name, "scriptFormat": "groovy"}
        if async_after:
            attrs[self.qn(CAMUNDA_NS, "asyncAfter")] = "true"
        if exclusive:
            attrs[self.qn(CAMUNDA_NS, "exclusive")] = "true"
        if result_variable:
            attrs[self.qn(CAMUNDA_NS, "resultVariable")] = result_variable

        task = ET.SubElement(self.process, self.qn(BPMN2_NS, "scriptTask"), attrs)

        # connector/IO script
        if connector:
            ext = ET.SubElement(task, self.qn(BPMN2_NS, "extensionElements"))
            connector_el = ET.SubElement(ext, self.qn(CAMUNDA_NS, "connector"))
            io = ET.SubElement(connector_el, self.qn(CAMUNDA_NS, "inputOutput"))

            # input parameter
            if connector_input_parameters:
                for param in connector_input_parameters:
                    input_param = ET.SubElement(
                        io,
                        self.qn(CAMUNDA_NS, "inputParameter"),
                        {"name": param["name"]},
                    )
                    if "value" in param:
                        input_param.text = param["value"]
                    if "map" in param:
                        header_map = ET.SubElement(
                            input_param, self.qn(CAMUNDA_NS, "map")
                        )
                        for k, v in param["map"].items():
                            ET.SubElement(
                                header_map, self.qn(CAMUNDA_NS, "entry"), {"key": k}
                            ).text = v

            # output parameter
            if connector_output_parameters:
                for param in connector_output_parameters:
                    op = ET.SubElement(
                        io,
                        self.qn(CAMUNDA_NS, "outputParameter"),
                        {"name": param["name"]},
                    )
                    if "script" in param:
                        script = ET.SubElement(
                            op,
                            self.qn(CAMUNDA_NS, "script"),
                            {"scriptFormat": param.get("scriptFormat", "groovy")},
                        )
                        script.text = param["script"]
                    elif "value" in param:
                        op.text = param["value"]

            ET.SubElement(
                connector_el, self.qn(CAMUNDA_NS, "connectorId")
            ).text = connector_id

        # normal script
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
        if not self.containsPlugin:
            self._create_service_task(
                createdeploym_id,
                "Create Deployment",
                async_after=True,
                exclusive=False,
                method="POST",
                url="http://${ipAdress}:${qunicornPort}/deployments/",
                extra_input_maps={
                    "headers": {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                },
                connector_payload_script=GroovyScript.PAYLOAD_CREATE_DEPLOYMENT_COMMON,
                connector_output_parameters=[
                    {
                        "name": "deploymentId",
                        "script": GroovyScript.OUTPUT_DEPLOYMENT_ID_COMMON,
                    },
                ],
            )

            self._create_service_task(
                exejob_id,
                "Execute Job",
                async_after=True,
                exclusive=False,
                method="POST",
                url="http://${ipAdress}:${qunicornPort}/jobs/",
                extra_input_maps={
                    "headers": {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                },
                connector_payload_script=GroovyScript.PAYLOAD_EXECUTE_JOB_COMMON,
                connector_output_parameters=[
                    {"name": "jobId", "script": GroovyScript.OUTPUT_JOB_ID_COMMON},
                ],
            )

            self._create_service_task(
                getjobres_id,
                "Get Job Results",
                async_after=True,
                exclusive=False,
                method="GET",
                url="http://${ipAdress}:${qunicornPort}/${jobId}",
                extra_input_maps={
                    "headers": {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                },
                connector_output_parameters=[
                    {
                        "name": "resultExecution",
                        "script": GroovyScript.OUTPUT_RESULT_EXECUTION_COMMON,
                    },
                    {
                        "name": "statusJob",
                        "script": GroovyScript.OUTPUT_STATUS_JOB_COMMON,
                    },
                ],
            )
            self._create_script_task(
                setvars2_id, "Set Variables", GroovyScript.SCRIPT_SET_VARS_COMMON
            )
        else:
            self._create_script_task(
                setvars2_id, "Set Variables", GroovyScript.SCRIPT_SET_VARS_CLUSTERING
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
            GroovyScript.SCRIPT_SET_CIRCUIT.format(qasmString=self.qasm_str),
            async_after=True,
            exclusive=True,
            result_variable="circuit",
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
            setvars1_id,
            "Set Variables",
            GroovyScript.SCRIPT_SET_VARS_PLACEHOLDER.format(jsonModel=self.model_json),
            result_variable="matrix",
        )

        self._create_service_task(
            backendreq_id,
            "Send Backend Request",
            async_after=True,
            exclusive=False,
            method="POST",
            url="http://${ipAdress}:${backendPort}/compile",
            extra_input_maps={
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            },
            connector_payload_script=GroovyScript.PAYLOAD_BACKEND_REQ_PLACEHOLDER,
            connector_output_parameters=[
                {"name": "uuid", "script": GroovyScript.OUTPUT_UUID_PLACEHOLDER}
            ],
        )

        self._create_service_task(
            pollstat_id,
            "Poll Status",
            async_after=True,
            exclusive=False,
            method="GET",
            url="http://${ipAdress}:${backendPort}/status/${uuid}",
            extra_input_maps={
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            },
            connector_output_parameters=[
                {
                    "name": "status",
                    "script": GroovyScript.OUTPUT_POLL_STATUS_PLACEHOLDER,
                }
            ],
        )

        self._create_service_task(
            retrievecirc_id,
            "Retrieve Circuit",
            async_after=True,
            exclusive=False,
            method="GET",
            url="http://${ipAdress}:${backendPort}/results/${uuid}",
            extra_input_maps={
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            },
            connector_output_parameters=[
                {"name": "circuit", "script": GroovyScript.OUTPUT_CIRCUIT_PLACEHOLDER}
            ],
        )

        self._create_exclusive_gateway(
            gateway1_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute
        self._create_exclusive_gateway(
            gateway2_id
        )  # gateway_default_targets is always empty at this stage therefore there will be no default attribute

        self._create_script_task(
            updatevars_id,
            "Update Variables",
            GroovyScript.SCRIPT_UPDATE_VARS_PLACEHOLDER,
            result_variable="matrix",
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

    def _create_chain_clustering(self, start_node: str, plugin_name: str) -> None:
        """
        Creates a clustering plugin execution chain.
        StartEvent -> Set Variables -> Call Clustering Plugin -> Poll Job Results -> Set Variables -> Analyze Results -> EndEvent
        """
        call_plugin_id = f"Task_{start_node}_call_plugin"
        poll_job_id = f"Task_{start_node}_poll_job_res"

        # Get inputs
        inputs = {}
        for node in self.start_event_classical_nodes:
            if node.type == "file":
                inputs["entityPointsUrl"] = node.value
            elif node.type == "int":
                if (
                    not self.containsPlaceholder
                ):  # placeholder is currently just available for number of clusters
                    inputs["numberOfClusters"] = int(node.value)
                else:
                    inputs["numberOfClusters"] = "${placeholder}"

        # Get needed parts from common parts
        (
            _,
            _,
            _,
            setvars2_id,
            gateway3_id,
            gateway4_id,
        ) = self._create_chain_common(start_node)

        # Specific parts
        task_name = self.get_plugin_task_name(plugin_name)

        file_url = inputs["entityPointsUrl"]
        num_clusters = inputs["numberOfClusters"]

        self._create_service_task(
            call_plugin_id,
            task_name,
            async_after=True,
            exclusive=False,
            method="POST",
            url="http://${ipAdress}:${pluginPort}/plugins/classical-k-means@v0-1-1/process/",
            extra_input_maps={
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            },
            connector_payload_script=GroovyScript.PAYLOAD_CALL_CLUSTERING.format(
                entityPointsUrl=file_url,
                numberOfClusters=num_clusters,
                maxIterations=inputs["maxIterations"]
                if "maxIterations" in inputs
                else "200",  # default value of maxIterations is 200
            ),
            connector_output_parameters=[
                {"name": "deploymentId", "script": GroovyScript.OUTPUT_CALL_CLUSTERING},
            ],
        )

        self._create_service_task(
            poll_job_id,
            "Poll Job Results",
            async_after=True,
            exclusive=False,
            method="GET",
            url="http://${ipAdress}:${pluginPort}/${deploymentId}",
            extra_input_maps={
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            },
            connector_output_parameters=[
                {
                    "name": "resultExecution",
                    "script": GroovyScript.OUTPUT_RESULT_CLUSTERING,
                },
                {"name": "statusJob", "script": GroovyScript.OUTPUT_STATUS_CLUSTERING},
            ],
        )

        self.inserted_chains[start_node] = (
            call_plugin_id,
            gateway3_id,
            poll_job_id,
            gateway4_id,
            setvars2_id,
        )

    def _create_sequence_flow(self, fid: str, src: str, tgt: str) -> None:
        """Helper to create a single Sequence Flow element."""
        # Resolve IDs
        # src/tgt are bare IDs (e.g. StartEvent_1) or task keys (Task_X)
        src_el_id = src
        tgt_el_id = tgt

        src_el = self.process.find(f".//*[@id='{src_el_id}']")
        tgt_el = self.process.find(f".//*[@id='{tgt_el_id}']")

        if tgt_el is not None:
            if tgt_el.tag != self.qn(BPMN2_NS, "startEvent"):
                ET.SubElement(tgt_el, self.qn(BPMN2_NS, "incoming")).text = fid
                self._fix_incoming_outgoing_order(tgt_el)
        if src_el is not None:
            if src_el.tag != self.qn(BPMN2_NS, "endEvent"):
                ET.SubElement(src_el, self.qn(BPMN2_NS, "outgoing")).text = fid
                self._fix_incoming_outgoing_order(src_el)

        sf = ET.SubElement(
            self.process,
            self.qn(BPMN2_NS, "sequenceFlow"),
            {"id": fid, "sourceRef": src_el_id, "targetRef": tgt_el_id},
        )

        # gateway conditions
        if src.endswith("_gateway_2"):
            cond = ET.SubElement(
                sf,
                self.qn(BPMN2_NS, "conditionExpression"),
                {self.qn(XSI_NS, "type"): "bpmn:tFormalExpression"},
            )
            if tgt.endswith("_retrieve_circuit"):
                cond.text = '${status == "completed"}'
            elif tgt.endswith("_update_vars"):
                cond.text = '${status != "completed" && iterations < 10}'
            elif tgt.endswith("_analyze_failed_transf"):
                cond.text = "${iterations >= 10}"
        elif src.endswith("_gateway_4"):
            cond = ET.SubElement(
                sf,
                self.qn(BPMN2_NS, "conditionExpression"),
                {self.qn(XSI_NS, "type"): "bpmn:tFormalExpression"},
            )
            if tgt.endswith("_analyze_failed_job"):
                cond.text = '${statusJob == "ERROR" || statusJob == "FAILURE"}'
            elif tgt.endswith("_gateway_3"):
                cond.text = '${statusJob != "ERROR" && statusJob != "FINISHED" && statusJob != "FAILURE" && statusJob != "SUCCESS"}'
            elif tgt.endswith("_set_vars_2"):
                cond.text = '${statusJob == "FINISHED" || statusJob == "SUCCESS"}'

    def get_plugin_task_name(self, plugin_name: str) -> str:
        name_map = {
            "classical-k-means": "Classical-K-Means",
            "classical-k-medoids": "Classical-K-Medoids",
            "quantum-k-means": "Quantum-K-Means",
        }
        readable = name_map.get(plugin_name, plugin_name.replace("-", " ").title())
        return f"Call {readable} Clustering"

    def extract_placeholder_values(self, model_json):
        """Extracts all the values of the int nodes if they are not an int"""
        model_obj = (
            json.loads(model_json) if isinstance(model_json, str) else model_json
        )
        if not isinstance(model_obj, dict):
            raise TypeError(f"model must be dict, got {type(model_obj).__name__}")

        nodes = model_obj.get("nodes", [])
        if not isinstance(nodes, list):
            raise TypeError(f"nodes must be list, got {type(nodes).__name__}")

        placeholders = []
        seen = set()

        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise TypeError(f"nodes[{i}] must be dict, got {type(node).__name__}")
            if node.get("type") == "int" and isinstance(node.get("value"), str):
                key = node["value"].strip()
                if key and key not in seen:
                    seen.add(key)
                    placeholders.append(key)

        return placeholders
