import React from 'react';
import ChatAgentConfig from '../ChatAgentConfig';

const DEFAULT_CONFIG = {
  name: 'pdf-chat',
  description: 'PDF Reading Assistant',
  provider_id: null,
  model_id: null,
  tools: ['read', 'library_search', 'library_read_note', 'memory_search', 'memory_read'],
  extensions: [],
  max_iterations: 10,
  temperature: 0.5,
  system_prompt: 'You are a helpful PDF reading assistant. You help users understand academic papers and documents by answering questions based on the provided context and your knowledge. You can search the knowledge base and read files to provide accurate answers. Be concise but thorough. When citing information from the PDF, reference the page number if available.',
  enabled: true,
};

function PdfChatAgentConfig({ sendWSMessage, enabledModels, availableTools, onSave }) {
  return (
    <ChatAgentConfig
      sendWSMessage={sendWSMessage}
      enabledModels={enabledModels}
      availableTools={availableTools}
      agentName="pdf-chat"
      title="PDF CHAT AGENT"
      defaultConfig={DEFAULT_CONFIG}
      onSave={onSave}
    />
  );
}

export default PdfChatAgentConfig;
