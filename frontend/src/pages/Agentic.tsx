import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AgenticAPI, JiraAPI } from '../lib/api'
import { useState } from 'react'
import SectionHeader from '../components/SectionHeader'

export default function Agentic() {
  const qc = useQueryClient()
  const [jiraKey, setJiraKey] = useState('')
  const [selectedWorkflow, setSelectedWorkflow] = useState<any>(null)
  const [config, setConfig] = useState<any>({
    create_pr: false,
    pr_draft: false,
    language: 'python',
    framework: 'fastapi',
    generate_tests: true,
    run_tests: true,
    validate_syntax: true,
    run_linters: true,
  })

  // Load default config
  const { data: defaultConfig } = useQuery({
    queryKey: ['agentic', 'config'],
    queryFn: () => AgenticAPI.getConfig(),
  })

  // Load workflows
  const { data: workflows = [], isLoading: workflowsLoading } = useQuery({
    queryKey: ['agentic', 'workflows'],
    queryFn: () => AgenticAPI.getWorkflows({ limit: 50 }),
    refetchInterval: 5000, // Refetch every 5 seconds to get updates
  })

  // Process workflow mutation
  const processWorkflow = useMutation({
    mutationFn: (async: boolean) => {
      if (async) {
        return AgenticAPI.processAsync({ jira_key: jiraKey, config })
      }
      return AgenticAPI.process({ jira_key: jiraKey, config })
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['agentic', 'workflows'] })
      if (data?.jira_key) {
        setSelectedWorkflow(data)
      }
      setJiraKey('')
    },
  })

  // Get status for a Jira key
  const getStatus = (key: string) => {
    return AgenticAPI.getStatus(key)
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'success': return 'bg-green-100 text-green-800'
      case 'failed': return 'bg-red-100 text-red-800'
      case 'partial': return 'bg-yellow-100 text-yellow-800'
      case 'started': return 'bg-blue-100 text-blue-800'
      case 'queued': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'success': return '✅'
      case 'failed': return '❌'
      case 'partial': return '⚠️'
      case 'started': return '🔄'
      case 'queued': return '⏳'
      default: return '⚪'
    }
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Agentic Code Generation"
        subtitle="Automatically generate code from Jira tickets"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Process Form */}
        <div className="space-y-4">
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Process Jira Ticket</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Jira Ticket Key
                </label>
                <input
                  type="text"
                  className="input w-full"
                  value={jiraKey}
                  onChange={(e) => setJiraKey(e.target.value.toUpperCase())}
                  placeholder="e.g., SCRUM-123"
                />
              </div>

              {/* Configuration Options */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium text-gray-800">Configuration</h3>
                
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.create_pr}
                      onChange={(e) => setConfig({ ...config, create_pr: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">Create PR</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.pr_draft}
                      onChange={(e) => setConfig({ ...config, pr_draft: e.target.checked })}
                      className="rounded"
                      disabled={!config.create_pr}
                    />
                    <span className="text-sm text-gray-700">Draft PR</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.generate_tests}
                      onChange={(e) => setConfig({ ...config, generate_tests: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">Generate Tests</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.run_tests}
                      onChange={(e) => setConfig({ ...config, run_tests: e.target.checked })}
                      className="rounded"
                      disabled={!config.generate_tests}
                    />
                    <span className="text-sm text-gray-700">Run Tests</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.validate_syntax}
                      onChange={(e) => setConfig({ ...config, validate_syntax: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">Validate Syntax</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={config.run_linters}
                      onChange={(e) => setConfig({ ...config, run_linters: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">Run Linters</span>
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Language
                  </label>
                  <select
                    className="input w-full"
                    value={config.language}
                    onChange={(e) => setConfig({ ...config, language: e.target.value })}
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="typescript">TypeScript</option>
                    <option value="java">Java</option>
                    <option value="go">Go</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Framework
                  </label>
                  <select
                    className="input w-full"
                    value={config.framework}
                    onChange={(e) => setConfig({ ...config, framework: e.target.value })}
                  >
                    <option value="fastapi">FastAPI</option>
                    <option value="django">Django</option>
                    <option value="flask">Flask</option>
                    <option value="express">Express</option>
                    <option value="react">React</option>
                    <option value="vue">Vue</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  className="btn-primary flex-1"
                  onClick={() => processWorkflow.mutate(false)}
                  disabled={!jiraKey.trim() || processWorkflow.isPending}
                >
                  {processWorkflow.isPending ? 'Processing...' : 'Process Now'}
                </button>
                <button
                  className="btn flex-1"
                  onClick={() => processWorkflow.mutate(true)}
                  disabled={!jiraKey.trim() || processWorkflow.isPending}
                >
                  {processWorkflow.isPending ? 'Queuing...' : 'Queue Async'}
                </button>
              </div>

              {processWorkflow.isError && (
                <div className="p-3 bg-red-50 text-red-800 rounded text-sm">
                  Error: {processWorkflow.error?.message || 'Failed to process workflow'}
                </div>
              )}

              {processWorkflow.isSuccess && (
                <div className="p-3 bg-green-50 text-green-800 rounded text-sm">
                  Workflow {processWorkflow.data?.status === 'queued' ? 'queued' : 'started'} successfully!
                </div>
              )}
            </div>
          </div>

          {/* Workflow History */}
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Recent Workflows</h2>
            {workflowsLoading ? (
              <div className="text-center py-8 text-gray-500">Loading workflows...</div>
            ) : workflows.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No workflows yet</div>
            ) : (
              <div className="space-y-3">
                {workflows.slice(0, 10).map((workflow: any) => (
                  <div
                    key={workflow._id || workflow.jira_key}
                    className="p-4 border rounded-lg hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => setSelectedWorkflow(workflow)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900">{workflow.jira_key}</span>
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(workflow.status)}`}>
                        {getStatusIcon(workflow.status)} {workflow.status}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">
                      {workflow.created_at ? new Date(workflow.created_at).toLocaleString() : 'Unknown date'}
                    </div>
                    {workflow.iterations && (
                      <div className="text-xs text-gray-500 mt-1">
                        Iterations: {workflow.iterations}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Workflow Details */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-800">Workflow Details</h2>
          {selectedWorkflow ? (
            <div className="card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold text-gray-900">{selectedWorkflow.jira_key}</h3>
                <span className={`px-3 py-1 text-sm rounded-full ${getStatusColor(selectedWorkflow.status)}`}>
                  {getStatusIcon(selectedWorkflow.status)} {selectedWorkflow.status}
                </span>
              </div>

              <div className="space-y-4">
                {/* Steps */}
                {selectedWorkflow.steps && Object.keys(selectedWorkflow.steps).length > 0 && (
                  <div>
                    <h4 className="font-medium text-gray-700 mb-3">Steps</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedWorkflow.steps).map(([stepName, stepData]: [string, any]) => (
                        <div key={stepName} className="p-3 bg-gray-50 rounded">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium text-gray-800 capitalize">
                              {stepName.replace(/_/g, ' ')}
                            </span>
                            {stepData.status && (
                              <span className={`px-2 py-1 text-xs rounded ${getStatusColor(stepData.status)}`}>
                                {stepData.status}
                              </span>
                            )}
                          </div>
                          {stepData.branch_name && (
                            <div className="text-sm text-gray-600">Branch: {stepData.branch_name}</div>
                          )}
                          {stepData.provider && (
                            <div className="text-sm text-gray-600">Provider: {stepData.provider}</div>
                          )}
                          {stepData.iterations && (
                            <div className="text-sm text-gray-600">Iterations: {stepData.iterations}</div>
                          )}
                          {stepData.pr_url && (
                            <div className="text-sm">
                              <a href={stepData.pr_url} target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline">
                                View Pull Request →
                              </a>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Errors */}
                {selectedWorkflow.errors && selectedWorkflow.errors.length > 0 && (
                  <div>
                    <h4 className="font-medium text-red-700 mb-2">Errors</h4>
                    <div className="space-y-1">
                      {selectedWorkflow.errors.map((error: string, idx: number) => (
                        <div key={idx} className="p-2 bg-red-50 text-red-800 text-sm rounded">
                          {error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Warnings */}
                {selectedWorkflow.warnings && selectedWorkflow.warnings.length > 0 && (
                  <div>
                    <h4 className="font-medium text-yellow-700 mb-2">Warnings</h4>
                    <div className="space-y-1">
                      {selectedWorkflow.warnings.map((warning: string, idx: number) => (
                        <div key={idx} className="p-2 bg-yellow-50 text-yellow-800 text-sm rounded">
                          {warning}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Code Generation Info */}
                {selectedWorkflow.steps?.code_generation && (
                  <div>
                    <h4 className="font-medium text-gray-700 mb-2">Code Generation</h4>
                    <div className="p-3 bg-gray-50 rounded text-sm">
                      <div>Provider: {selectedWorkflow.steps.code_generation.provider || 'Unknown'}</div>
                      <div>Iterations: {selectedWorkflow.steps.code_generation.iterations || 0}</div>
                      {selectedWorkflow.steps.code_generation.generated_code?.notes && (
                        <div className="mt-2">
                          <div className="font-medium mb-1">Notes:</div>
                          <ul className="list-disc list-inside space-y-1">
                            {selectedWorkflow.steps.code_generation.generated_code.notes.map((note: string, idx: number) => (
                              <li key={idx}>{note}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Test Results */}
                {selectedWorkflow.steps?.testing && (
                  <div>
                    <h4 className="font-medium text-gray-700 mb-2">Test Results</h4>
                    <div className="p-3 bg-gray-50 rounded text-sm">
                      {selectedWorkflow.steps.testing.test_results ? (
                        <>
                          <div>Tests: {selectedWorkflow.steps.testing.test_results.test_count || 0}</div>
                          <div>Passed: {selectedWorkflow.steps.testing.test_results.passed || 0}</div>
                          <div>Failed: {selectedWorkflow.steps.testing.test_results.failed || 0}</div>
                          {selectedWorkflow.steps.testing.test_results.success ? (
                            <div className="text-green-700 font-medium mt-2">✓ All tests passed</div>
                          ) : (
                            <div className="text-red-700 font-medium mt-2">✗ Some tests failed</div>
                          )}
                        </>
                      ) : (
                        <div>Tests not run</div>
                      )}
                    </div>
                  </div>
                )}

                {/* Validation Results */}
                {selectedWorkflow.steps?.validation && (
                  <div>
                    <h4 className="font-medium text-gray-700 mb-2">Validation</h4>
                    <div className="p-3 bg-gray-50 rounded text-sm">
                      <div>Syntax Valid: {selectedWorkflow.steps.validation.syntax_valid ? '✓' : '✗'}</div>
                      <div>Linter Passed: {selectedWorkflow.steps.validation.linter_passed ? '✓' : '✗'}</div>
                      {selectedWorkflow.steps.validation.syntax_errors?.length > 0 && (
                        <div className="mt-2 text-red-700">
                          Syntax Errors: {selectedWorkflow.steps.validation.syntax_errors.length}
                        </div>
                      )}
                      {selectedWorkflow.steps.validation.linter_errors?.length > 0 && (
                        <div className="mt-2 text-red-700">
                          Linter Errors: {selectedWorkflow.steps.validation.linter_errors.length}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Metadata */}
                <div className="pt-4 border-t">
                  <div className="text-sm text-gray-600 space-y-1">
                    <div>Created: {selectedWorkflow.created_at ? new Date(selectedWorkflow.created_at).toLocaleString() : 'Unknown'}</div>
                    {selectedWorkflow.iterations && (
                      <div>Iterations: {selectedWorkflow.iterations}</div>
                    )}
                    {selectedWorkflow.max_iterations_reached && (
                      <div className="text-yellow-700 font-medium">⚠ Max iterations reached</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card p-6 text-center">
              <div className="text-gray-500">Select a workflow to view details</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}



