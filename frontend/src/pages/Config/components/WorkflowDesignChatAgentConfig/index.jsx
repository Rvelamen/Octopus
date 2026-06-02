import React from 'react';
import ChatAgentConfig from '../ChatAgentConfig';

const DEFAULT_CONFIG = {
  name: 'workflow-designer',
  description: 'Workflow design assistant',
  provider_id: null,
  model_id: null,
  tools: [
    'add_node', 'connect_nodes', 'set_variable', 'remove_node', 'update_node',
    'auto_layout', 'validate_workflow', 'run_test', 'get_variable_context',
    'get_node_io', 'get_nodes', 'list_database_tables',
    'add_input_variable', 'add_output_variable', 'remove_variable',
  ],
  extensions: [],
  max_iterations: 15,
  temperature: 0.3,
  system_prompt: 'You are a workflow design expert for the Octopus platform. Your job is to help users create and modify visual workflows by calling tools.',
  enabled: true,
};

function WorkflowDesignChatAgentConfig({ sendWSMessage, enabledModels, availableTools, onSave }) {
  return (
    <ChatAgentConfig
      sendWSMessage={sendWSMessage}
      enabledModels={enabledModels}
      availableTools={availableTools}
      agentName="workflow-designer"
      title="WORKFLOW DESIGN AGENT"
      defaultConfig={DEFAULT_CONFIG}
      onSave={onSave}
    />
  );
}

export default WorkflowDesignChatAgentConfig;
