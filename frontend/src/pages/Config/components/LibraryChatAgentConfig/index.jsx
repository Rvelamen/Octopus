import React from 'react';
import ChatAgentConfig from '../ChatAgentConfig';

const DEFAULT_CONFIG = {
  name: 'library-chat',
  description: 'Library knowledge assistant',
  provider_id: null,
  model_id: null,
  tools: ['read', 'list', 'library_search', 'library_read_note', 'library_list_links', 'library_timeline', 'memory_search', 'memory_read'],
  extensions: [],
  max_iterations: 10,
  temperature: 0.5,
  system_prompt: 'You are a helpful Library knowledge assistant. You help users understand and analyze academic papers and documents in their library collection. You can search library notes, read PDFs, list directories, and explore note relationships to provide accurate answers.',
  enabled: true,
};

function LibraryChatAgentConfig({ sendWSMessage, enabledModels, availableTools, onSave }) {
  return (
    <ChatAgentConfig
      sendWSMessage={sendWSMessage}
      enabledModels={enabledModels}
      availableTools={availableTools}
      agentName="library-chat"
      title="LIBRARY CHAT AGENT"
      defaultConfig={DEFAULT_CONFIG}
      onSave={onSave}
    />
  );
}

export default LibraryChatAgentConfig;
