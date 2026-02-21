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

SCRIPT_SET_VARS_PLACEHOLDER = """def model= '{"metadata":{"optimizeWidth":null,"optimizeDepth":null,"version":"1.0.0","name":"My Model","description":"This is a model.","author":"","containsPlaceholder":false},"compilation_target":"qasm","nodes":[{"id":"1a1f4fe0-9c18-4956-a394-c6326ab10f80","label":null,"type":"qubit","size":1},{"id":"1d9e5132-79f3-475d-ba91-7e63b89fef85","label":null,"type":"gate","gate":"h"}],"edges":[{"source":["1a1f4fe0-9c18-4956-a394-c6326ab10f80",0],"target":["1d9e5132-79f3-475d-ba91-7e63b89fef85",0],"size":null,"identifier":null}]}'
execution.setVariable("model", model)
def groupId = execution.getVariable("groupId")
println "groupId: ${groupId}"

if (!groupId){
    execution.setVariable("groupId", 0)
}else{
    execution.setVariable("groupId", groupId+1)
}

def iterations = execution.getVariable("iterations")

if (!iterations){
    execution.setVariable("iterations", 0)
} else {
    execution.setVariable("iterations", iterations+1)
}"""

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
println "Response: ${resp}"
resp = new groovy.json.JsonSlurper().parseText(resp)
println("Response to extract status: " + resp.toString());
status= resp.get('state')
println(status);
return status;"""

OUTPUT_CIRCUIT_PLACEHOLDER = """return connector.getVariable("response")"""

SCRIPT_UPDATE_VARS_PLACEHOLDER = """def iterations= execution.getVariable("iterations")
execution.setVariable("iterations", iterations+1)"""

SCRIPT_LOAD_FILE_CLUSTERING = '''execution.setVariable("circuit", """OPENQASM 3.1;
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
print "Set Variables"
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

def resp = new JsonSlurper()
    .parseText(connector.getVariable("response"))
println "Response to extract resultExecution: ${resp}"

return resp.toString()"""
