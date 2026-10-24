"""
Support for :class:`~app.model.CompileRequest.ApiConnectorNode`.

API connectors cannot be compiled into OpenQASM.
For the workflow target each of them becomes a service task with a Camunda
http-connector, i.e. the request is sent by the engine itself::

    <camunda:connector>
      <camunda:inputOutput>
        <camunda:inputParameter name="method">POST</camunda:inputParameter>
        <camunda:inputParameter name="headers"><camunda:map>...</camunda:map></camunda:inputParameter>
        <camunda:inputParameter name="url">...</camunda:inputParameter>
        <camunda:inputParameter name="payload"><camunda:script>...</camunda:script></camunda:inputParameter>
        <camunda:outputParameter name="..."><camunda:script>...</camunda:script></camunda:outputParameter>
      </camunda:inputOutput>
      <camunda:connectorId>http-connector</camunda:connectorId>
    </camunda:connector>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.model.CompileRequest import ApiConnectorNode

CONNECTOR_ID = "http-connector"


def is_api_connector(node: object) -> bool:
    """
    Check whether the node is an :class:`~app.model.CompileRequest.ApiConnectorNode`.
    """
    return isinstance(node, ApiConnectorNode)


def api_connector_task_id(node_id: str) -> str:
    """
    ID of the BPMN service task created for an API connector node.
    """
    return f"Task_{node_id}_api_connector"


def add_http_connector(
    extension_elements: ET.Element, node: ApiConnectorNode, camunda_ns: str
) -> ET.Element:
    """
    Append the ``<camunda:connector>`` of the node to the ``extensionElements`` of a service task.
    """

    def qn(tag: str) -> str:
        return f"{{{camunda_ns}}}{tag}"

    connector = ET.SubElement(extension_elements, qn("connector"))
    io = ET.SubElement(connector, qn("inputOutput"))

    def input_parameter(name: str) -> ET.Element:
        return ET.SubElement(io, qn("inputParameter"), {"name": name})

    input_parameter("method").text = node.method

    headers = {key: value for key, value in node.headers.items() if key.strip()}
    if headers:
        header_map = ET.SubElement(input_parameter("headers"), qn("map"))
        for key, value in headers.items():
            ET.SubElement(header_map, qn("entry"), {"key": key}).text = value

    input_parameter("url").text = node.url

    if node.payload is not None and node.method != "GET":
        ET.SubElement(
            input_parameter("payload"),
            qn("script"),
            {"scriptFormat": node.scriptFormat},
        ).text = node.payload

    for output in node.outputs:
        if not output.name.strip():
            continue
        parameter = ET.SubElement(io, qn("outputParameter"), {"name": output.name})
        ET.SubElement(
            parameter, qn("script"), {"scriptFormat": node.scriptFormat}
        ).text = output.script

    ET.SubElement(connector, qn("connectorId")).text = CONNECTOR_ID
    return connector
