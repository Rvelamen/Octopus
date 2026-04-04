import React from 'react';
import { MessageSquare } from 'lucide-react';
import MessageItem from './MessageItem';
import ToolCard from './ToolCard';
import ToolCardGroup from './ToolCardGroup';
import CompressionSummary from './CompressionSummary';
import octopusAvatar from '../../../../../assets/images/octopus.png';
import './MessageList.css';

function MessageList({
  messages,
  streamingContent,
  toolCalls,
  toolCallAssistantContents,
  messageTtsMap,
  selectedInstance,
  currentChatInstanceId,
  onImageClick,
  renderMessageContent
}) {
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const pairToolMessages = (messages, hideToolPairs = false) => {
    const pairs = [];
    const toolResults = new Map();
    const seenMessages = new Set();
    let iterationCount = 0;

    messages.forEach(msg => {
      const toolCallId = msg.metadata?.tool_call_id || msg.tool_call_id;
      if (toolCallId && (msg.role === 'tool' || msg.message_type === 'tool_result')) {
        toolResults.set(toolCallId, msg);
      }
    });

    messages.forEach(msg => {
      const msgKey = `${msg.role}:${msg.content}:${msg.timestamp}`;
      if (seenMessages.has(msgKey)) {
        return;
      }
      seenMessages.add(msgKey);

      if (msg.metadata?.is_summary || msg.metadata?.message_type === 'context_summary') {
        pairs.push({
          type: 'compression_summary',
          message: msg,
          compressionInfo: msg.metadata?.compression_info || {}
        });
        return;
      }

      const toolCalls = msg.metadata?.tool_calls || msg.tool_calls;
      if (toolCalls && toolCalls.length > 0) {
        if (hideToolPairs) {
          return;
        }
        
        iterationCount++;
        const tools = toolCalls.map((tc, index) => {
          const callId = tc?.id;
          const result = toolResults.get(callId);
          return {
            toolCallId: callId,
            toolName: tc?.function?.name,
            toolCall: tc,
            args: tc?.function?.arguments || '{}',
            result: result?.content,
            status: result ? 'completed' : 'pending',
            toolIndex: index,
            totalTools: toolCalls.length
          };
        });
        
        pairs.push({
          type: 'tool_group',
          iteration: iterationCount,
          assistantContent: msg.content,
          tools: tools
        });
      } else if (!msg.metadata?.tool_call_id && !msg.tool_call_id) {
        pairs.push({ type: 'normal', message: msg });
      }
    });

    return pairs;
  };

  const renderToolGroup = (pair) => {
    return (
      <div key={`tool-group-${pair.iteration}`} className="tool-message-wrapper">
        <ToolCardGroup
          tools={pair.tools}
          assistantContent={pair.assistantContent}
          iteration={pair.iteration}
          renderMessageContent={renderMessageContent}
        />
      </div>
    );
  };

  const isStreaming = streamingContent && streamingContent.length > 0;
  const hasActiveToolCalls = toolCalls && toolCalls.length > 0 && selectedInstance?.id === currentChatInstanceId;
  const pairedMessages = pairToolMessages(messages, isStreaming || hasActiveToolCalls);

  return (
    <div className="messages-list">
      {pairedMessages.map((pair, idx) => {
        if (pair.type === 'compression_summary') {
          return (
            <CompressionSummary
              key={pair.message.id || idx}
              message={pair.message}
              compressionInfo={pair.compressionInfo}
              formatTime={formatTime}
              renderMessageContent={renderMessageContent}
            />
          );
        } else if (pair.type === 'tool_group') {
          return renderToolGroup(pair);
        } else {
          const msg = pair.message;
          const msgTts = messageTtsMap[msg.id];

          return (
            <MessageItem
              key={msg.id || idx}
              message={msg}
              ttsAudio={msgTts}
              onImageClick={onImageClick}
              renderMessageContent={renderMessageContent}
            />
          );
        }
      })}

      {(() => {
        if (!toolCalls || toolCalls.length === 0 || selectedInstance?.id !== currentChatInstanceId) {
          return null;
        }
        
        const iterationGroups = {};
        toolCalls.forEach(tc => {
          const iter = tc.iteration || 1;
          if (!iterationGroups[iter]) {
            iterationGroups[iter] = [];
          }
          iterationGroups[iter].push(tc);
        });
        
        return Object.entries(iterationGroups).map(([iteration, calls]) => (
          <div key={`iteration-${iteration}`} className="tool-iteration-group">
            {calls.map((toolCall, idx) => (
              <div key={toolCall.id || idx} className="tool-message-wrapper">
                <ToolCard
                  toolCallId={`live-${toolCall.id}`}
                  toolName={toolCall.tool}
                  args={toolCall.args}
                  partialArgs={toolCall.partialArgs}  // 传递流式参数
                  result={toolCall.result}
                  status={toolCall.status}
                  error={toolCall.error}  // 传递错误信息
                  assistantContent={idx === 0 ? toolCallAssistantContents[iteration] : null}
                  toolIndex={idx}
                  totalTools={calls.length}
                  renderMessageContent={renderMessageContent}
                />
              </div>
            ))}
          </div>
        ));
      })()}

      {streamingContent && selectedInstance?.id === currentChatInstanceId && (
        <div className="message-row message-row-assistant streaming">
          <div className="message-bubble message-bubble-assistant">
            <div className="message-bubble-header">
              <div className="message-bubble-avatar">
                <img src={octopusAvatar} className="avatar-assistant-img" alt="Octopus" />
              </div>
              <div className="message-bubble-meta">
                <span className="message-bubble-author">Octopus</span>
                <span className="message-bubble-time streaming-indicator">
                  <span className="blink">streaming</span>
                </span>
              </div>
            </div>
            <div className="message-bubble-content">
              {renderMessageContent(streamingContent)}
              <span className="cursor-blink">_</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MessageList;
