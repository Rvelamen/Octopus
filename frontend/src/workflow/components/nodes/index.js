import { memo } from 'react';

import WorkflowStart from './WorkflowStart/Node';
import WorkflowEnd from './WorkflowEnd/Node';
import CodeNode from './CodeNode/Node';
import SelectorNode from './SelectorNode/Node';
import LoopNode from './LoopNode/Node';
import InputNode from './InputNode/Node';
import OutputNode from './OutputNode/Node';
import LLMNode from './LLMNode/Node';
import HTTPNode from './HTTPNode/Node';
import JSONSerializeNode from './JSONSerializeNode/Node';
import JSONDeserializeNode from './JSONDeserializeNode/Node';
import TextNode from './TextNode/Node';
import { withTestButton } from './withTestButton';

const nodeTypes = {
  workflowStart: withTestButton(memo(WorkflowStart)),
  workflowEnd: withTestButton(memo(WorkflowEnd)),
  code: withTestButton(memo(CodeNode)),
  ifElseNode: withTestButton(memo(SelectorNode)),
  loop: withTestButton(memo(LoopNode)),
  inputNode: withTestButton(memo(InputNode)),
  pluginOutput: withTestButton(memo(OutputNode)),
  llm: withTestButton(memo(LLMNode)),
  chatNode: withTestButton(memo(LLMNode)),
  http: withTestButton(memo(HTTPNode)),
  textEditor: withTestButton(memo(TextNode)),
  jsonSerialize: withTestButton(memo(JSONSerializeNode)),
  jsonDeserialize: withTestButton(memo(JSONDeserializeNode)),
};

export default nodeTypes;
