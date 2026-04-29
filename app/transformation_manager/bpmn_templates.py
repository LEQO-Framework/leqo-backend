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

// parse model
def modelObj = new JsonSlurper().parseText(modelStr)

// set the compilation_target to qasm
modelObj.compilation_target = "qasm"

// replace int node values with the placeholder values dynamically
modelObj.nodes.each {{ node ->
    if (node.type == "int" && (node.value instanceof String)) {{
        def placeholderName = node.value
        def placeholderValue = execution.getVariable(placeholderName)

        if (placeholderValue != null && placeholderValue.toString().trim() != "") {{
            node.value = placeholderValue
        }} else {{
            throw new RuntimeException("Missing value for placeholder: " + placeholderName)
        }}
    }}
}}

// json back to string
def model = new JsonBuilder(modelObj).toPrettyString()
execution.setVariable("model", model)

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

SCRIPT_SET_CIRCUIT = '''execution.setVariable("circuit", """{qasmString}""")'''

OUTPUT_PARAM_LOAD_FILE_CLUSTERING = """def resp = connector.getVariable("response");
println("Response")
println(response)

return response;"""

PAYLOAD_CALL_CLUSTERING = """import java.net.URLEncoder

def uri = "{entityPointsUrl}"
def numClusters = {numberOfClustersExpr}
def maxIter = {maxIterationsExpr}
def relativeResidual = {relativeResidualExpr}
def minSamples = {minSamplesExpr}
def minClusterSize = {minClusterSizeExpr}
def leafSize = {leafSizeExpr}
def epsilon = {epsilonExpr}
def minSteepness = {minSteepnessExpr}
if (numClusters == null || numClusters.toString().trim().isEmpty()) {{
    numClusters = 3
}}
if (relativeResidual == null || relativeResidual.toString().trim().isEmpty()) {{
    relativeResidual = 5
}}
if (maxIter == null || maxIter.toString().trim().isEmpty()) {{
    maxIter = 200
}}
def tolerance = {toleranceExpr}
if (tolerance == null || tolerance.toString().trim().isEmpty()) {{
    tolerance = 0.0
}}
def maxEps = {maxEpsilonExpr}
if (maxEps == null || maxEps.toString().trim().isEmpty()) {{
    maxEps = -1
}}

def data = [
{dataBlock}
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
