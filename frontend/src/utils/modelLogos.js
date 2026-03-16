// Model Logo Mapping
// Maps model IDs/names to their logo image paths

import DeepSeekModelLogo from '../assets/images/models/deepseek.png'
import QwenModelLogo from '../assets/images/models/qwen.png'
import ClaudeModelLogo from '../assets/images/models/claude.png'
import ChatGPT4ModelLogo from '../assets/images/models/gpt_4.png'
import ChatGPT35ModelLogo from '../assets/images/models/gpt_3.5.png'
import ChatGptModelLogo from '../assets/images/models/chatgpt.jpeg'
import ChatGPTo1ModelLogo from '../assets/images/models/gpt_o1.png'
import ChatGPTImageModelLogo from '../assets/images/models/gpt_image_1.png'
import GPT5ModelLogo from '../assets/images/models/gpt-5.png'
import GPT5ChatModelLogo from '../assets/images/models/gpt-5-chat.png'
import GPT5MiniModelLogo from '../assets/images/models/gpt-5-mini.png'
import GPT5NanoModelLogo from '../assets/images/models/gpt-5-nano.png'
import GPT5CodexModelLogo from '../assets/images/models/gpt-5-codex.png'
import GPT51ModelLogo from '../assets/images/models/gpt-5.1.png'
import GPT51ChatModelLogo from '../assets/images/models/gpt-5.1-chat.png'
import GPT51CodexModelLogo from '../assets/images/models/gpt-5.1-codex.png'
import GPT51CodexMiniModelLogo from '../assets/images/models/gpt-5.1-codex-mini.png'
import GeminiModelLogo from '../assets/images/models/gemini.png'
import MoonshotModelLogo from '../assets/images/models/moonshot.webp'
import BaichuanModelLogo from '../assets/images/models/baichuan.png'
import ChatGLMModelLogo from '../assets/images/models/chatglm.png'
import ZhipuModelLogo from '../assets/images/models/zhipu.png'
import YiModelLogo from '../assets/images/models/yi.png'
import LlamaModelLogo from '../assets/images/models/llama.png'
import MistralModelLogo from '../assets/images/models/mixtral.png'
import CodestralModelLogo from '../assets/images/models/codestral.png'
import GrokModelLogo from '../assets/images/models/grok.png'
import DoubaoModelLogo from '../assets/images/models/doubao.png'
import MinimaxModelLogo from '../assets/images/models/minimax.png'
import StepModelLogo from '../assets/images/models/step.png'
import HunyuanModelLogo from '../assets/images/models/hunyuan.png'
import CohereModelLogo from '../assets/images/models/cohere.png'
import Ai21ModelLogo from '../assets/images/models/ai21.png'
import DalleModelLogo from '../assets/images/models/dalle.png'
import DbrxModelLogo from '../assets/images/models/dbrx.png'
import FluxModelLogo from '../assets/images/models/flux.png'
import StableDiffusionModelLogo from '../assets/images/models/stability.png'
import MidjourneyModelLogo from '../assets/images/models/midjourney.png'
import LumaModelLogo from '../assets/images/models/luma.png'
import ViduModelLogo from '../assets/images/models/vidu.png'
import SunoModelLogo from '../assets/images/models/suno.png'
import HailuoModelLogo from '../assets/images/models/hailuo.png'
import KelingModelLogo from '../assets/images/models/keling.png'
import SparkDeskModelLogo from '../assets/images/models/sparkdesk.png'
import InternLMModelLogo from '../assets/images/models/internlm.png'
import QwenVLModelLogo from '../assets/images/models/internvl.png'
import NvidiaModelLogo from '../assets/images/models/nvidia.png'
import MicrosoftModelLogo from '../assets/images/models/microsoft.png'
import GoogleModelLogo from '../assets/images/models/google.png'
import GemmaModelLogo from '../assets/images/models/gemma.png'
import PerplexityModelLogo from '../assets/images/models/perplexity.png'
import JinaModelLogo from '../assets/images/models/jina.png'
import VoyageModelLogo from '../assets/images/models/voyageai.png'
import BgeModelLogo from '../assets/images/models/bge.webp'
import NomicModelLogo from '../assets/images/providers/nomic.png'
import PanguModelLogo from '../assets/images/models/pangu.svg'
import WenxinModelLogo from '../assets/images/models/wenxin.png'
import EmbeddingModelLogo from '../assets/images/models/embedding.png'
import Ai360ModelLogo from '../assets/images/models/360.png'
import CodegeexModelLogo from '../assets/images/models/codegeex.png'
import CopilotModelLogo from '../assets/images/models/copilot.png'
import HuggingfaceModelLogo from '../assets/images/models/huggingface.png'
import XirangModelLogo from '../assets/images/models/xirang.png'
import TeleModelLogo from '../assets/images/models/tele.png'
import DianxinModelLogo from '../assets/images/models/dianxin.png'
import AdeptModelLogo from '../assets/images/models/adept.png'
import AiMassModelLogo from '../assets/images/models/aimass.png'
import AiSingaporeModelLogo from '../assets/images/models/aisingapore.png'
import BigcodeModelLogo from '../assets/images/models/bigcode.webp'
import GrypheModelLogo from '../assets/images/models/gryphe.png'
import IbmModelLogo from '../assets/images/models/ibm.png'
import MediatekModelLogo from '../assets/images/models/mediatek.png'
import NousResearchModelLogo from '../assets/images/models/nousresearch.png'
import PalmModelLogo from '../assets/images/models/palm.png'
import PixtralModelLogo from '../assets/images/models/pixtral.png'
import RakutenaiModelLogo from '../assets/images/models/rakutenai.png'
import UpstageModelLogo from '../assets/images/models/upstage.png'
import FlashaudioModelLogo from '../assets/images/models/flashaudio.png'
import MagicModelLogo from '../assets/images/models/magic.png'
import TokenFluxModelLogo from '../assets/images/models/tokenflux.png'
import LLavaModelLogo from '../assets/images/models/llava.png'
import MinicpmModelLogo from '../assets/images/models/minicpm.webp'
import MiMoModelLogo from '../assets/images/models/mimo.svg'
import IdeogramModelLogo from '../assets/images/models/ideogram.svg'
import BytedanceModelLogo from '../assets/images/models/byte_dance.svg'
import LingModelLogo from '../assets/images/models/ling.png'

// Model logo map - uses regex patterns as keys for flexible matching
const MODEL_LOGO_MAP = [
  { pattern: /gpt-5\.1-codex-mini/i, logo: GPT51CodexMiniModelLogo },
  { pattern: /gpt-5\.1-codex/i, logo: GPT51CodexModelLogo },
  { pattern: /gpt-5\.1-chat/i, logo: GPT51ChatModelLogo },
  { pattern: /gpt-5\.1/i, logo: GPT51ModelLogo },
  { pattern: /gpt-5-mini/i, logo: GPT5MiniModelLogo },
  { pattern: /gpt-5-nano/i, logo: GPT5NanoModelLogo },
  { pattern: /gpt-5-chat/i, logo: GPT5ChatModelLogo },
  { pattern: /gpt-5-codex/i, logo: GPT5CodexModelLogo },
  { pattern: /gpt-5/i, logo: GPT5ModelLogo },
  { pattern: /gpt-?image/i, logo: ChatGPTImageModelLogo },
  { pattern: /gpt-?4/i, logo: ChatGPT4ModelLogo },
  { pattern: /gpt-?3\.5/i, logo: ChatGPT35ModelLogo },
  { pattern: /o1|o3|o4/i, logo: ChatGPTo1ModelLogo },
  { pattern: /gpt-?oss/i, logo: ChatGptModelLogo },
  { pattern: /text-moderation|babbage|davinci|tts|whisper|omni/i, logo: ChatGptModelLogo },
  { pattern: /sora/i, logo: ChatGptModelLogo },
  { pattern: /dall-?e/i, logo: DalleModelLogo },
  { pattern: /claude|anthropic/i, logo: ClaudeModelLogo },
  { pattern: /gemini|palm|bison/i, logo: GeminiModelLogo },
  { pattern: /gemma/i, logo: GemmaModelLogo },
  { pattern: /google/i, logo: GoogleModelLogo },
  { pattern: /veo/i, logo: GeminiModelLogo },
  { pattern: /deepseek/i, logo: DeepSeekModelLogo },
  { pattern: /qwen|qwq|qvq|wan-/i, logo: QwenModelLogo },
  { pattern: /glm|chatglm|zhipu|cogview/i, logo: ChatGLMModelLogo },
  { pattern: /yi-/i, logo: YiModelLogo },
  { pattern: /moonshot|kimi/i, logo: MoonshotModelLogo },
  { pattern: /baichuan/i, logo: BaichuanModelLogo },
  { pattern: /llama/i, logo: LlamaModelLogo },
  { pattern: /mixtral|mistral|codestral|ministral|magistral/i, logo: MistralModelLogo },
  { pattern: /pixtral/i, logo: PixtralModelLogo },
  { pattern: /grok/i, logo: GrokModelLogo },
  { pattern: /doubao|seedream|ep-202/i, logo: DoubaoModelLogo },
  { pattern: /bytedance/i, logo: BytedanceModelLogo },
  { pattern: /minimax|abab|m2-her/i, logo: MinimaxModelLogo },
  { pattern: /step/i, logo: StepModelLogo },
  { pattern: /hunyuan/i, logo: HunyuanModelLogo },
  { pattern: /cohere|command/i, logo: CohereModelLogo },
  { pattern: /ai21|jamba/i, logo: Ai21ModelLogo },
  { pattern: /flux/i, logo: FluxModelLogo },
  { pattern: /stable-?diffusion|sd2|sd3|sdxl/i, logo: StableDiffusionModelLogo },
  { pattern: /midjourney|mj-/i, logo: MidjourneyModelLogo },
  { pattern: /luma/i, logo: LumaModelLogo },
  { pattern: /vidu/i, logo: ViduModelLogo },
  { pattern: /ideogram/i, logo: IdeogramModelLogo },
  { pattern: /suno|chirp/i, logo: SunoModelLogo },
  { pattern: /hailuo/i, logo: HailuoModelLogo },
  { pattern: /flashaudio|voice/i, logo: FlashaudioModelLogo },
  { pattern: /keling/i, logo: KelingModelLogo },
  { pattern: /sparkdesk|generalv/i, logo: SparkDeskModelLogo },
  { pattern: /internlm/i, logo: InternLMModelLogo },
  { pattern: /internvl/i, logo: QwenVLModelLogo },
  { pattern: /llava/i, logo: LLavaModelLogo },
  { pattern: /minicpm/i, logo: MinicpmModelLogo },
  { pattern: /nvidia/i, logo: NvidiaModelLogo },
  { pattern: /microsoft|phi|wizardlm/i, logo: MicrosoftModelLogo },
  { pattern: /jina/i, logo: JinaModelLogo },
  { pattern: /perplexity|sonar/i, logo: PerplexityModelLogo },
  { pattern: /voyage/i, logo: VoyageModelLogo },
  { pattern: /bge/i, logo: BgeModelLogo },
  { pattern: /nomic/i, logo: NomicModelLogo },
  { pattern: /text-embedding|embedding/i, logo: EmbeddingModelLogo },
  { pattern: /wenxin|ernie|tao-/i, logo: WenxinModelLogo },
  { pattern: /pangu/i, logo: PanguModelLogo },
  { pattern: /tele/i, logo: TeleModelLogo },
  { pattern: /dianxin/i, logo: DianxinModelLogo },
  { pattern: /360/i, logo: Ai360ModelLogo },
  { pattern: /codegeex/i, logo: CodegeexModelLogo },
  { pattern: /copilot|creative|balanced|precise/i, logo: CopilotModelLogo },
  { pattern: /hugging/i, logo: HuggingfaceModelLogo },
  { pattern: /xirang/i, logo: XirangModelLogo },
  { pattern: /adept/i, logo: AdeptModelLogo },
  { pattern: /aimass/i, logo: AiMassModelLogo },
  { pattern: /aisingapore/i, logo: AiSingaporeModelLogo },
  { pattern: /bigcode/i, logo: BigcodeModelLogo },
  { pattern: /gryphe|mythomax/i, logo: GrypheModelLogo },
  { pattern: /hermes/i, logo: NousResearchModelLogo },
  { pattern: /ibm/i, logo: IbmModelLogo },
  { pattern: /mediatek/i, logo: MediatekModelLogo },
  { pattern: /rakutenai/i, logo: RakutenaiModelLogo },
  { pattern: /upstage/i, logo: UpstageModelLogo },
  { pattern: /magic/i, logo: MagicModelLogo },
  { pattern: /tokenflux/i, logo: TokenFluxModelLogo },
  { pattern: /mimo/i, logo: MiMoModelLogo },
  { pattern: /ling|ring/i, logo: LingModelLogo },
]

/**
 * Get model logo by model ID or name
 * @param {string} modelId - Model ID or name
 * @returns {string|undefined} - Logo image path or undefined
 */
export function getModelLogo(modelId) {
  if (!modelId || typeof modelId !== 'string') return undefined
  
  const normalizedId = modelId.toLowerCase().trim()
  
  for (const { pattern, logo } of MODEL_LOGO_MAP) {
    if (pattern.test(normalizedId)) {
      return logo
    }
  }
  
  return undefined
}

/**
 * Get model logo from model object
 * @param {Object} model - Model object with id and/or name
 * @returns {string|undefined} - Logo image path or undefined
 */
export function getModelLogoFromObject(model) {
  if (!model || typeof model !== 'object') return undefined
  
  return getModelLogo(model.modelId) || getModelLogo(model.id) || getModelLogo(model.displayName) || getModelLogo(model.name)
}

export default {
  getModelLogo,
  getModelLogoFromObject,
}
