# Free AI Models for RAG Workflows

## Overview

This guide recommends the best **free, API-accessible** models for your biomedical troubleshooting agent.

## Reasoning Models (for Hypothesis Generation)

### Top Recommendation: Groq (Free Tier)

| Provider | Model | Context | Free Limit | Best For |
|----------|-------|---------|------------|----------|
| **Groq** | `llama-3.3-70b-versatile` | 128K | 100K tokens/day | Fast reasoning |
| Groq | `mixtral-8x7b-32768` | 32K | 100K tokens/day | Complex logic |

**Why Groq:**
- Truly free API (no credit card)
- Extremely fast inference (ideal for interactive troubleshooting)
- Supports structured outputs
- Excellent for domain-specific reasoning

**Setup:**
```bash
export GROQ_API_KEY="your-groq-api-key"
pip install groq
```

**Usage:**
```python
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You are a biomedical equipment expert..."},
        {"role": "user", "content": "Analyze these signal measurements..."}
    ]
)
```

### Alternatives (Free Tier)

| Provider | Model | Free Limit | Notes |
|----------|-------|------------|-------|
| **OpenAI** | `gpt-4o-mini` | $100/1st month only | Requires credit card |
| **Anthropic** | `claude-sonnet-4` | $5 free/month | Credit card required |
| **Google** | `gemini-2.0-flash-exp` | 1500 req/day | Free tier available |
| **HuggingFace** | `Zephyr-7B-beta` | Free inference API | Rate limited |

## Embedding Models (for RAG)

### Top Recommendation: HuggingFace Inference API (Free)

| Model | Dimensions | Performance | Free Limit |
|-------|-----------|-------------|------------|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Good | 1000 req/day |
| `BAAI/bge-small-en-v1.5` | 384 | Very Good | 1000 req/day |
| `WhereIsAI/UAE-Large-V1.5` | 1024 | Excellent | 500 req/day |

**Setup:**
```bash
pip install sentence-transformers
```

**Usage:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
embeddings = model.encode(["troubleshooting power supply"])
```

### Alternative: OpenAI Embeddings (Paid Tier)

| Model | Dimensions | Cost |
|-------|------------|------|
| `text-embedding-3-small` | 1536 | $0.02/1M tokens |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens |

## Recommended Stack

### For Your Biomedical Troubleshooting Agent

```
Reasoning:  Groq + llama-3.3-70b-versatile (FREE)
Embeddings: HuggingFace + bge-small-en-v1.5 (FREE)
Vector DB:  ChromaDB (local, free)
Tracing:    LangSmith (free tier)
```

### .env Configuration

```bash
# Reasoning (Groq - FREE)
GROQ_API_KEY=your-groq-api-key
LLM_MODEL=llama-3.3-70b-versatile
LLM_PROVIDER=groq

# Embeddings (HuggingFace - FREE)
HF_API_KEY=your-hf-token
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_PROVIDER=huggingface

# Optional: OpenAI (Paid fallback)
OPENAI_API_KEY=your-openai-key
```

## Rate Limits & Production Use

### Groq (Recommended)
- **Free tier:** 100K tokens/day
- **Rate limit:** 60 requests/minute
- **Production:** Apply for higher limits

### HuggingFace Inference
- **Free tier:** 1000 requests/day
- **Rate limit:** 3 requests/second
- **Production:** Upgrade to Pro ($9/mo)

## Integration with Your Agent

Update `src/infrastructure/config.py`:

```python
def get_llm_config() -> LLMConfig:
    provider = os.environ.get("LLM_PROVIDER", "groq")
    if provider == "groq":
        return LLMConfig(
            provider="groq",
            api_key=os.environ.get("GROQ_API_KEY"),
            model=os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
        )
    # Fallback to OpenAI
    return LLMConfig.from_env()
```

## Comparison Summary

| Use Case | Best Free Option | Paid Alternative |
|----------|------------------|------------------|
| Reasoning/Chat | Groq + Llama 3.3 | OpenAI GPT-4o |
| Embeddings | HuggingFace BGE | OpenAI text-embedding-3 |
| Speed | Groq (fastest) | - |
| Quality | Claude 3.5 (paid) | Groq (free) |
| Domain Expert | Fine-tuned Llama (DIY) | GPT-4o |

## Getting Started

1. **Groq:** https://console.groq.com (sign up, get free API key)
2. **HuggingFace:** https://huggingface.co/settings/tokens (generate token)
3. **Update .env:**
   ```bash
   GROQ_API_KEY=your-groq-key
   HF_API_KEY=your-hf-token
   ```

## Model Comparison for Biomedical Domain

For troubleshooting biomedical equipment, reasoning quality matters:

| Model | Medical QA | Technical | Speed |
|-------|-------------|-----------|-------|
| Llama 3.3 70B | Good | Very Good | Fast |
| Claude 3.5 | Excellent | Excellent | Medium |
| Gemini 2.0 | Good | Good | Fast |
| Mixtral 8x7B | Good | Good | Fast |

**Recommendation:** Start with Groq + Llama 3.3 70B for best speed/quality balance on free tier.
