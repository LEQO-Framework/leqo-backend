"""
Groovy script templates for BPMN service tasks.
"""

PAYLOAD_CREATE_DEPLOYMENT_COMMON = """import groovy.json.JsonBuilder

def circuit = execution.getVariable("circuit")
println "Circuit: ${circuit}"

def program = [
    programs: [
        [
            quantumCircuit: circuit,
            assemblerLanguage: "QASM3",
            pythonFilePath: "",
            pythonFileMetadata: ""
        ]
    ],
    name: "DeploymentName"
]

println "program: ${program}"

return new JsonBuilder(program).toPrettyString()"""

OUTPUT_DEPLOYMENT_ID_COMMON = """import groovy.json.JsonSlurper

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
    
println "Response: ${resp}"

return resp.id"""

PAYLOAD_EXECUTE_JOB_COMMON = """import groovy.json.JsonBuilder

def deploymentId = execution.getVariable("deploymentId")
println "deploymentId: ${deploymentId}"

def program = [
    name           : "JobName",
    providerName   : "IBM",
    deviceName     : "aer_simulator",
    shots          : 1024,
    errorMitigation: "none",
    cutToWidth     : null,
    token          : "",
    type           : "RUNNER",
    deploymentId   : deploymentId
]

def requestString = new JsonBuilder(program).toPrettyString()
println "RequestString"
println requestString

return requestString"""

OUTPUT_JOB_ID_COMMON = """import groovy.json.JsonSlurper

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
println "Response: ${resp}"

return resp.self"""

OUTPUT_RESULT_EXECUTION_COMMON = """import groovy.json.JsonSlurper
import groovy.json.JsonBuilder

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
println "Response: ${resp}"

return new JsonBuilder(resp.results).toString()"""

OUTPUT_STATUS_JOB_COMMON = """import groovy.json.JsonSlurper

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
println "Response: ${resp}"

return resp.state"""

SCRIPT_SET_VARS_PLACEHOLDER = """
import groovy.json.JsonSlurper
import groovy.json.JsonBuilder

// get origin model
def modelStr = '{jsonModel}'
def placeholder = execution.getVariable("placeholder")

// parse model
def modelObj = new JsonSlurper().parseText(modelStr)

// set the compilation_target to qasm
modelObj.compilation_target = "qasm"

// replace the placeholder within the int node with the users input
modelObj.nodes.each {{ node ->
    if (node.type == "int" && (node.value instanceof String)) {{
        node.value = placeholder
    }}
}}

// json back to string
def model = new JsonBuilder(modelObj).toPrettyString()
execution.setVariable("model", model)

println("placeholder: ${{placeholder}}")
def groupId = execution.getVariable("groupId")
println "groupId: ${{groupId}}"

if (!groupId) {{
    execution.setVariable("groupId", 0)
}} else {{
    execution.setVariable("groupId", groupId+1)
}}

def iterations = execution.getVariable("iterations")

if (!iterations) {{
    execution.setVariable("iterations", 0)
}} else {{
    execution.setVariable("iterations", iterations+1)
}}
"""

SCRIPT_SET_VARS_COMMON = """def groupId = execution.getVariable("groupId")
if (groupId == null) {
    groupId = 1
}
groupId = groupId + 1"""

PAYLOAD_BACKEND_REQ_PLACEHOLDER = """import groovy.json.JsonSlurper
import groovy.json.JsonBuilder
def modelStr = execution.getVariable("model")
println(modelStr)

def modelObj = new JsonSlurper().parseText(modelStr)

def requestString = new JsonBuilder(modelObj).toPrettyString()
println("===============================")
println(requestString)
return requestString"""

OUTPUT_UUID_PLACEHOLDER = """def resp = connector.getVariable("response");
println "Response: ${resp}"
resp = new groovy.json.JsonSlurper().parseText(resp)
println("Response to extract uuid: " + resp.toString());
uuid= resp.get('uuid')
println(uuid);
return uuid;"""

# Backend
OUTPUT_STATUS_PLACEHOLDER = """def resp = connector.getVariable("response");
println("Response")
println(response)
resp = new groovy.json.JsonSlurper().parseText(resp)
println("Response to extract statusJob: " + resp.toString());
statusJob= resp.get('state')
println(statusJob);
return statusJob;"""

OUTPUT_POLL_STATUS_PLACEHOLDER = """def resp = connector.getVariable("response");
println("Response")
println(response)
resp = new groovy.json.JsonSlurper().parseText(resp)
println("Response to extract status: " + resp.toString());
status= resp.get('status')
println(status);
return status;"""

OUTPUT_CIRCUIT_PLACEHOLDER = """return connector.getVariable("response")"""

SCRIPT_UPDATE_VARS_PLACEHOLDER = """def iterations= execution.getVariable("iterations")
execution.setVariable("iterations", iterations+1)"""

SCRIPT_SET_CIRCUIT = '''execution.setVariable("circuit", """OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
/* Start node e1239b18-6fa4-465e-86ef-dfd16700149a */
let leqo_8573d7eea9f659f79ebf928b67848931_literal = leqo_reg[{0}];
@leqo.output 0
let leqo_8573d7eea9f659f79ebf928b67848931_out = leqo_8573d7eea9f659f79ebf928b67848931_literal;
/* End node e1239b18-6fa4-465e-86ef-dfd16700149a */
/* Start node 71c72e1a-079c-4909-8a60-66080da29177 */
@leqo.input 0
let leqo_239a05e84bdc5dde96f076fcd88cbadf_q0 = leqo_reg[{0}];
h leqo_239a05e84bdc5dde96f076fcd88cbadf_q0;
@leqo.output 0
let leqo_239a05e84bdc5dde96f076fcd88cbadf_q0_out = leqo_239a05e84bdc5dde96f076fcd88cbadf_q0;
/* End node 71c72e1a-079c-4909-8a60-66080da29177 */
/* Start node 9c2ea4d5-60c4-4353-9ac7-2a5e66760bd7 */
@leqo.input 0
let leqo_d8d0d6144e55565e92223d41f2bd2f7c_q = leqo_reg[{0}];
bit[1] leqo_d8d0d6144e55565e92223d41f2bd2f7c_result = measure leqo_d8d0d6144e55565e92223d41f2bd2f7c_q[{0}];
@leqo.output 0
let leqo_d8d0d6144e55565e92223d41f2bd2f7c_out = leqo_d8d0d6144e55565e92223d41f2bd2f7c_result;
@leqo.output 1
let leqo_d8d0d6144e55565e92223d41f2bd2f7c_qubit_out = leqo_d8d0d6144e55565e92223d41f2bd2f7c_q;
/* End node 9c2ea4d5-60c4-4353-9ac7-2a5e66760bd7 */
""")'''

OUTPUT_PARAM_LOAD_FILE_CLUSTERING = """def resp = connector.getVariable("response");
println("Response")
println(response)

return response;"""

PAYLOAD_CALL_CLUSTERING = """import java.net.URLEncoder

def uri = "{entityPointsUrl}"

def data = [
    "entityPointsUrl=${{URLEncoder.encode(uri, 'UTF-8')}}",
    "numClusters={numberOfClusters}",
    "maxiter={maxIterations}",
    "relativeResidual=5",
    "visualize=true",
]

def formData = data.join('&')

println "=================== REQUEST ==================="
println formData

formData"""

OUTPUT_CALL_CLUSTERING = """println "=================== RESPONSE ==================="
println "Status Code: ${statusCode}"
println "Headers: ${headers}"
println "Body: ${response}"
println "================================================"

// Location Header für Redirect holen
def redirectUrl = null

if (statusCode == 303 || statusCode == 301 || statusCode == 302) {
// Location Header auslesen
redirectUrl = headers?.get('Location') ?: headers?.get('location')
println "Redirect URL: ${redirectUrl}"
}

redirectUrl"""


OUTPUT_STATUS_JOB_COMMON = """println("Response")
println(response)
resp = new groovy.json.JsonSlurper().parseText(response)
println("Response to extract statusJob: " + resp.toString());
statusJob= resp.get('state')
println(statusJob);
return statusJob;"""

SCRIPT_SET_VARS_CLUSTERING = """
import groovy.json.JsonOutput
def resultExecution = execution.getVariable("resultExecution")
def result = new groovy.json.JsonSlurper().parseText(resultExecution)
result.outputs.eachWithIndex { output, i ->
    execution.setVariable("outputHref_${i}", output.href)
}
"""

OUTPUT_STATUS_CLUSTERING = """println("Response")
println(response)
resp = new groovy.json.JsonSlurper().parseText(response)
println("Response to extract statusJob: " + resp.toString());
statusJob= resp.get('status')
println(statusJob);
return statusJob;"""

OUTPUT_RESULT_CLUSTERING = """import groovy.json.JsonSlurper
import groovy.json.JsonBuilder
import groovy.json.JsonOutput

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
println "Response to extract resultExecution: ${resp}"
def json = JsonOutput.prettyPrint(JsonOutput.toJson(resp))

return json"""

AGENTIC_INPUT = """You are a helpful, generic chat agent which can answer a wide amount of questions based on your knowledge and an optional set of available tools.

If tools are provided, you should prefer them instead of guessing an answer. You can call the same tool multiple times by providing different input values. Don't guess any tools which were not explicitely configured. If no tool matches the request, try to generate an answer. If you're not able to find a good answer, return with a message stating why you're not able to.

If you are prompted to interact with a person, never guess contact details, but use available user/person lookup tools instead and return with an error if you're not able to look up appropriate data.

Thinking, step by step, before you execute your tools, you think using the template `<thinking><context></context><reflection></reflection></thinking>`"""

AGENTIC_MODELER_TEMPLATE_ICON = """data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9
IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTYiIGN5PSIxNi
Igcj0iMTYiIGZpbGw9IiNBNTZFRkYiLz4KPG1hc2sgaWQ9InBhdGgtMi1vdXRzaWRlLTFfMTg1XzYiIG1hc2tVbml0cz0idXNlclNwYWNlT25Vc
2UiIHg9IjQiIHk9IjQiIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgZmlsbD0iYmxhY2siPgo8cmVjdCBmaWxsPSJ3aGl0ZSIgeD0iNCIgeT0iNCIg
d2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ii8+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMjAuMDEwNSA
xMi4wOTg3QzE4LjQ5IDEwLjU4OTQgMTcuMTU5NCA4LjEwODE0IDE2LjE3OTkgNi4wMTEwM0MxNi4xNTIgNi4wMDQ1MSAxNi4xMTc2IDYgMTYuMD
c5NCA2QzE2LjA0MTEgNiAxNi4wMDY2IDYuMDA0NTEgMTUuOTc4OCA2LjAxMTA0QzE0Ljk5OTQgOC4xMDgxNCAxMy42Njk3IDEwLjU4ODkgMTIuM
TQ4MSAxMi4wOTgxQzEwLjYyNjkgMTMuNjA3MSA4LjEyNTY4IDE0LjkyNjQgNi4wMTE1NyAxNS44OTgxQzYuMDA0NzQgMTUuOTI2MSA2IDE1Ljk2
MTEgNiAxNkM2IDE2LjAzODcgNi4wMDQ2OCAxNi4wNzM2IDYuMDExNDQgMTYuMTAxNEM4LjEyNTE5IDE3LjA3MjkgMTAuNjI2MiAxOC4zOTE5IDE
yLjE0NzcgMTkuOTAxNkMxMy42Njk3IDIxLjQxMDcgMTQuOTk5NiAyMy44OTIgMTUuOTc5MSAyNS45ODlDMTYuMDA2OCAyNS45OTU2IDE2LjA0MT
EgMjYgMTYuMDc5MyAyNkMxNi4xMTc1IDI2IDE2LjE1MTkgMjUuOTk1NCAxNi4xNzk2IDI1Ljk4OUMxNy4xNTkxIDIzLjg5MiAxOC40ODg4IDIxL
jQxMSAyMC4wMDk5IDE5LjkwMjFNMjAuMDA5OSAxOS45MDIxQzIxLjUyNTMgMTguMzk4NyAyMy45NDY1IDE3LjA2NjkgMjUuOTkxNSAxNi4wODI0
QzI1Ljk5NjUgMTYuMDU5MyAyNiAxNi4wMzEgMjYgMTUuOTk5N0MyNiAxNS45Njg0IDI1Ljk5NjUgMTUuOTQwMyAyNS45OTE1IDE1LjkxNzFDMjM
uOTQ3NCAxNC45MzI3IDIxLjUyNTkgMTMuNjAxIDIwLjAxMDUgMTIuMDk4NyIvPgo8L21hc2s+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2
xpcC1ydWxlPSJldmVub2RkIiBkPSJNMjAuMDEwNSAxMi4wOTg3QzE4LjQ5IDEwLjU4OTQgMTcuMTU5NCA4LjEwODE0IDE2LjE3OTkgNi4wMTEwM
0MxNi4xNTIgNi4wMDQ1MSAxNi4xMTc2IDYgMTYuMDc5NCA2QzE2LjA0MTEgNiAxNi4wMDY2IDYuMDA0NTEgMTUuOTc4OCA2LjAxMTA0QzE0Ljk5O
TQgOC4xMDgxNCAxMy42Njk3IDEwLjU4ODkgMTIuMTQ4MSAxMi4wOTgxQzEwLjYyNjkgMTMuNjA3MSA4LjEyNTY4IDE0LjkyNjQgNi4wMTE1NyAxN
S44OTgxQzYuMDA0NzQgMTUuOTI2MSA2IDE1Ljk2MTEgNiAxNkM2IDE2LjAzODcgNi4wMDQ2OCAxNi4wNzM2IDYuMDExNDQgMTYuMTAxNEM4LjEyNT
E5IDE3LjA3MjkgMTAuNjI2MiAxOC4zOTE5IDEyLjE0NzcgMTkuOTAxNkMxMy42Njk3IDIxLjQxMDcgMTQuOTk5NiAyMy44OTIgMTUuOTc5MSAyNS
45ODlDMTYuMDA2OCAyNS45OTU2IDE2LjA0MTEgMjYgMTYuMDc5MyAyNkMxNi4xMTc1IDI2IDE2LjE1MTkgMjUuOTk1NCAxNi4xNzk2IDI1Ljk4OUM
xNy4xNTkxIDIzLjg5MiAxOC40ODg4IDIxLjQxMSAyMC4wMDk5IDE5LjkwMjFNMjAuMDA5OSAxOS45MDIxQzIxLjUyNTMgMTguMzk4NyAyMy45NDY1
IDE3LjA2NjkgMjUuOTkxNSAxNi4wODI0QzI1Ljk5NjUgMTYuMDU5MyAyNiAxNi4wMzEgMjYgMTUuOTk5N0MyNiAxNS45Njg0IDI1Ljk5NjUgMTUuO
TQwMyAyNS45OTE1IDE1LjkxNzFDMjMuOTQ3NCAxNC45MzI3IDIxLjUyNTkgMTMuNjAxIDIwLjAxMDUgMTIuMDk4NyIgZmlsbD0id2hpdGUiLz4KPH
BhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik0yMC4wMTA1IDEyLjA5ODdDMTguNDkgMTAuNTg5NCAxNy4xNTk
0IDguMTA4MTQgMTYuMTc5OSA2LjAxMTAzQzE2LjE1MiA2LjAwNDUxIDE2LjExNzYgNiAxNi4wNzk0IDZDMTYuMDQxMSA2IDE2LjAwNjYgNi4wMDQ1
MSAxNS45Nzg4IDYuMDExMDRDMTQuOTk5NCA4LjEwODE0IDEzLjY2OTcgMTAuNTg4OSAxMi4xNDgxIDEyLjA5ODFDMTAuNjI2OSAxMy42MDcxIDguM
TI1NjggMTQuOTI2NCA2LjAxMTU3IDE1Ljg5ODFDNi4wMDQ3NCAxNS45MjYxIDYgMTUuOTYxMSA2IDE2QzYgMTYuMDM4NyA2LjAwNDY4IDE2LjA3Mz
YgNi4wMTE0NCAxNi4xMDE0QzguMTI1MTkgMTcuMDcyOSAxMC42MjYyIDE4LjM5MTkgMTIuMTQ3NyAxOS45MDE2QzEzLjY2OTcgMjEuNDEwNyAxNC4
5OTk2IDIzLjg5MiAxNS45NzkxIDI1Ljk4OUMxNi4wMDY4IDI1Ljk5NTYgMTYuMDQxMSAyNiAxNi4wNzkzIDI2QzE2LjExNzUgMjYgMTYuMTUxOSAy
NS45OTU0IDE2LjE3OTYgMjUuOTg5QzE3LjE1OTEgMjMuODkyIDE4LjQ4ODggMjEuNDExIDIwLjAwOTkgMTkuOTAyMU0yMC4wMDk5IDE5LjkwMjFDM
jEuNTI1MyAxOC4zOTg3IDIzLjk0NjUgMTcuMDY2OSAyNS45OTE1IDE2LjA4MjRDMjUuOTk2NSAxNi4wNTkzIDI2IDE2LjAzMSAyNiAxNS45OTk3Qz
I2IDE1Ljk2ODQgMjUuOTk2NSAxNS45NDAzIDI1Ljk5MTUgMTUuOTE3MUMyMy45NDc0IDE0LjkzMjcgMjEuNTI1OSAxMy42MDEgMjAuMDEwNSAxMi4
wOTg3IiBzdHJva2U9IiM0OTFEOEIiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgbWFzaz0idXJsKCNwYXRoLTItb3V0
c2lkZS0xXzE4NV82KSIvPgo8L3N2Zz4K"""