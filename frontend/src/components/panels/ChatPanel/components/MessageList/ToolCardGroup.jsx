import React from 'react';
import ToolCard from './ToolCard';

function ToolCardGroup({
  tools,
  assistantContent,
  iteration,
  renderMessageContent
}) {
  return (
    <div className="tool-card-group">
      {assistantContent && (
        <div className="tool-card-group-header">
          <div className="tool-card-group-assistant-content">
            {renderMessageContent(assistantContent)}
          </div>
        </div>
      )}

      <div className="tool-card-group-content">
        {tools.map((tool, idx) => (
          <ToolCard
            key={tool.toolCallId || idx}
            toolCallId={tool.toolCallId}
            toolName={tool.toolName}
            args={tool.args}
            result={tool.result}
            status={tool.status}
            assistantContent={null}
            toolIndex={idx}
            totalTools={tools.length}
            renderMessageContent={renderMessageContent}
          />
        ))}
      </div>
    </div>
  );
}

export default ToolCardGroup;
