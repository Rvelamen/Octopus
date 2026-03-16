// Provider Logo Mapping
// Maps provider names/IDs to their logo image paths

import OpenAiProviderLogo from '../assets/images/providers/openai.png'
import AnthropicProviderLogo from '../assets/images/providers/anthropic.png'
import DeepSeekProviderLogo from '../assets/images/providers/deepseek.png'
import ZhipuProviderLogo from '../assets/images/providers/zhipu.png'
import GoogleProviderLogo from '../assets/images/providers/google.png'
import AzureProviderLogo from '../assets/images/providers/microsoft.png'
import OllamaProviderLogo from '../assets/images/providers/ollama.png'
import MoonshotProviderLogo from '../assets/images/providers/moonshot.webp'
import BaichuanProviderLogo from '../assets/images/providers/baichuan.png'
import DashscopeProviderLogo from '../assets/images/providers/dashscope.png'
import SiliconFlowProviderLogo from '../assets/images/providers/silicon.png'
import StepfunProviderLogo from '../assets/images/providers/step.png'
import DoubaoProviderLogo from '../assets/images/providers/volcengine.png'
import MinimaxProviderLogo from '../assets/images/providers/minimax.png'
import GroqProviderLogo from '../assets/images/providers/groq.png'
import TogetherProviderLogo from '../assets/images/providers/together.png'
import FireworksProviderLogo from '../assets/images/providers/fireworks.png'
import PerplexityProviderLogo from '../assets/images/providers/perplexity.png'
import MistralProviderLogo from '../assets/images/providers/mistral.png'
import CohereProviderLogo from '../assets/images/providers/cohere.png'
import Ai21ProviderLogo from '../assets/images/providers/ai21.png'
import GrokProviderLogo from '../assets/images/providers/grok.png'
import NvidiaProviderLogo from '../assets/images/providers/nvidia.png'
import OpenRouterProviderLogo from '../assets/images/providers/openrouter.png'
import GithubProviderLogo from '../assets/images/providers/github.png'
import HuggingfaceProviderLogo from '../assets/images/providers/huggingface.webp'
import JinaProviderLogo from '../assets/images/providers/jina.png'
import VoyageAIProviderLogo from '../assets/images/providers/voyageai.png'
import QiniuProviderLogo from '../assets/images/providers/qiniu.webp'
import PPIOProviderLogo from '../assets/images/providers/ppio.png'
import CerebrasProviderLogo from '../assets/images/providers/cerebras.webp'
import Ai302ProviderLogo from '../assets/images/providers/302ai.webp'
import AiHubMixProviderLogo from '../assets/images/providers/aihubmix.webp'
import BurnCloudProviderLogo from '../assets/images/providers/burncloud.png'
import OcoolAiProviderLogo from '../assets/images/providers/ocoolai.png'
import LMStudioProviderLogo from '../assets/images/providers/lmstudio.png'
import NewAPIProviderLogo from '../assets/images/providers/newapi.png'
import TokenFluxProviderLogo from '../assets/images/providers/tokenflux.png'
import LongCatProviderLogo from '../assets/images/providers/longcat.png'
import SophnetProviderLogo from '../assets/images/providers/sophnet.svg'
import HyperbolicProviderLogo from '../assets/images/providers/hyperbolic.png'
import InfiniProviderLogo from '../assets/images/providers/infini.png'
import BaiduCloudProviderLogo from '../assets/images/providers/baidu-cloud.svg'
import TencentCloudTIProviderLogo from '../assets/images/providers/tencent-cloud-ti.png'
import VertexAIProviderLogo from '../assets/images/providers/vertexai.svg'
import AwsBedrockProviderLogo from '../assets/images/providers/aws-bedrock.webp'
import MiMoProviderLogo from '../assets/images/providers/mimo.svg'
import ModelScopeProviderLogo from '../assets/images/providers/modelscope.png'
import XirangProviderLogo from '../assets/images/providers/xirang.png'
import HunyuanProviderLogo from '../assets/images/providers/hunyuan.png'
import GiteeAIProviderLogo from '../assets/images/providers/gitee-ai.png'
import ZeroOneProviderLogo from '../assets/images/providers/zero-one.png'
import ZaiProviderLogo from '../assets/images/providers/zai.svg'
import AlayaNewProviderLogo from '../assets/images/providers/alayanew.webp'
import DMXAPIProviderLogo from '../assets/images/providers/DMXAPI.png'
import CephalonProviderLogo from '../assets/images/providers/cephalon.jpeg'
import LanyunProviderLogo from '../assets/images/providers/lanyun.png'
import Ph8ProviderLogo from '../assets/images/providers/ph8.png'
import O3ProviderLogo from '../assets/images/providers/o3.png'
import AIGatewayProviderLogo from '../assets/images/providers/vercel.svg'
import GPUStackProviderLogo from '../assets/images/providers/gpustack.svg'
import IntelOvmsProviderLogo from '../assets/images/providers/intel.png'
import CherryInProviderLogo from '../assets/images/providers/cherryin.png'
import AiOnlyProviderLogo from '../assets/images/providers/aiOnly.webp'

// Provider logo map - maps provider ID/name to logo
export const PROVIDER_LOGO_MAP = {
  openai: OpenAiProviderLogo,
  anthropic: AnthropicProviderLogo,
  deepseek: DeepSeekProviderLogo,
  zhipu: ZhipuProviderLogo,
  google: GoogleProviderLogo,
  gemini: GoogleProviderLogo,
  azure: AzureProviderLogo,
  'azure-openai': AzureProviderLogo,
  ollama: OllamaProviderLogo,
  moonshot: MoonshotProviderLogo,
  baichuan: BaichuanProviderLogo,
  dashscope: DashscopeProviderLogo,
  bailian: DashscopeProviderLogo,
  silicon: SiliconFlowProviderLogo,
  siliconflow: SiliconFlowProviderLogo,
  stepfun: StepfunProviderLogo,
  step: StepfunProviderLogo,
  doubao: DoubaoProviderLogo,
  volcengine: DoubaoProviderLogo,
  bytedance: DoubaoProviderLogo,
  minimax: MinimaxProviderLogo,
  groq: GroqProviderLogo,
  together: TogetherProviderLogo,
  fireworks: FireworksProviderLogo,
  perplexity: PerplexityProviderLogo,
  mistral: MistralProviderLogo,
  cohere: CohereProviderLogo,
  ai21: Ai21ProviderLogo,
  grok: GrokProviderLogo,
  xai: GrokProviderLogo,
  nvidia: NvidiaProviderLogo,
  openrouter: OpenRouterProviderLogo,
  github: GithubProviderLogo,
  copilot: GithubProviderLogo,
  huggingface: HuggingfaceProviderLogo,
  jina: JinaProviderLogo,
  voyageai: VoyageAIProviderLogo,
  voyage: VoyageAIProviderLogo,
  qiniu: QiniuProviderLogo,
  ppio: PPIOProviderLogo,
  cerebras: CerebrasProviderLogo,
  '302ai': Ai302ProviderLogo,
  '302': Ai302ProviderLogo,
  aihubmix: AiHubMixProviderLogo,
  burncloud: BurnCloudProviderLogo,
  ocoolai: OcoolAiProviderLogo,
  lmstudio: LMStudioProviderLogo,
  'new-api': NewAPIProviderLogo,
  newapi: NewAPIProviderLogo,
  tokenflux: TokenFluxProviderLogo,
  longcat: LongCatProviderLogo,
  sophnet: SophnetProviderLogo,
  hyperbolic: HyperbolicProviderLogo,
  infini: InfiniProviderLogo,
  'baidu-cloud': BaiduCloudProviderLogo,
  baidu: BaiduCloudProviderLogo,
  qianfan: BaiduCloudProviderLogo,
  'tencent-cloud-ti': TencentCloudTIProviderLogo,
  tencent: TencentCloudTIProviderLogo,
  hunyuan: HunyuanProviderLogo,
  vertexai: VertexAIProviderLogo,
  vertex: VertexAIProviderLogo,
  'aws-bedrock': AwsBedrockProviderLogo,
  bedrock: AwsBedrockProviderLogo,
  mimo: MiMoProviderLogo,
  xiaomimimo: MiMoProviderLogo,
  modelscope: ModelScopeProviderLogo,
  xirang: XirangProviderLogo,
  ctyun: XirangProviderLogo,
  giteeai: GiteeAIProviderLogo,
  'gitee-ai': GiteeAIProviderLogo,
  zeroone: ZeroOneProviderLogo,
  '01-ai': ZeroOneProviderLogo,
  yi: ZeroOneProviderLogo,
  zai: ZaiProviderLogo,
  alayanew: AlayaNewProviderLogo,
  dmxapi: DMXAPIProviderLogo,
  cephalon: CephalonProviderLogo,
  lanyun: LanyunProviderLogo,
  ph8: Ph8ProviderLogo,
  o3: O3ProviderLogo,
  gateway: AIGatewayProviderLogo,
  'ai-gateway': AIGatewayProviderLogo,
  gpustack: GPUStackProviderLogo,
  ovms: IntelOvmsProviderLogo,
  intel: IntelOvmsProviderLogo,
  cherryin: CherryInProviderLogo,
  aionly: AiOnlyProviderLogo,
  'ai-only': AiOnlyProviderLogo,
}

/**
 * Get provider logo by provider ID or name
 * @param {string} providerId - Provider ID or name
 * @returns {string|undefined} - Logo image path or undefined
 */
export function getProviderLogo(providerId) {
  if (!providerId || typeof providerId !== 'string') return undefined
  
  const normalizedId = providerId.toLowerCase().trim()
  
  if (PROVIDER_LOGO_MAP[normalizedId]) {
    return PROVIDER_LOGO_MAP[normalizedId]
  }
  
  for (const [key, logo] of Object.entries(PROVIDER_LOGO_MAP)) {
    if (normalizedId.includes(key) || key.includes(normalizedId)) {
      return logo
    }
  }
  
  return undefined
}

export default {
  PROVIDER_LOGO_MAP,
  getProviderLogo,
}
