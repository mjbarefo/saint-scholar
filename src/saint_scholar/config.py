# Saint & Scholar — Central Configuration

# Embedding
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking
KNOWLEDGE_CHUNK_SIZE = 500       # tokens — abstracts are small, often 1 chunk
STYLE_CHUNK_SIZE = 300           # tokens
STYLE_CHUNK_OVERLAP = 50         # tokens

# Retrieval
KNOWLEDGE_TOP_K = 5
STYLE_TOP_K = 3

# Local vector store
VECTOR_STORE_DIR = "./vector_store"

# Generation
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

# Figures (display config)
FIGURES = {
    "buddha": {
        "name": "Buddha",
        "tradition": "Buddhism",
        "tagline": "Calm parables & the path to understanding",
        "icon": "🪷",
        "color": "#F59E0B"    # warm amber
    },
    "aurelius": {
        "name": "Marcus Aurelius",
        "tradition": "Stoicism",
        "tagline": "Stern self-interrogation & duty",
        "icon": "🏛️",
        "color": "#6B7280"    # stone gray
    },
    "rumi": {
        "name": "Rumi",
        "tradition": "Sufism",
        "tagline": "Ecstatic wonder & metaphor",
        "icon": "🌀",
        "color": "#8B5CF6"    # deep violet
    },
    "solomon": {
        "name": "Solomon",
        "tradition": "Wisdom Literature",
        "tagline": "World-weary wisdom & cycles of time",
        "icon": "👑",
        "color": "#D97706"    # burnished gold
    },
    "laotzu": {
        "name": "Lao Tzu",
        "tradition": "Taoism",
        "tagline": "Paradox, nature & the way of wu wei",
        "icon": "☯",
        "color": "#059669"    # jade green
    },
    "epictetus": {
        "name": "Epictetus",
        "tradition": "Stoicism",
        "tagline": "Freedom through mastery of what is within your control",
        "icon": "⛓️",
        "color": "#6366F1"    # indigo
    },
    "seneca": {
        "name": "Seneca",
        "tradition": "Stoicism",
        "tagline": "Letters on the art of living well",
        "icon": "✒️",
        "color": "#8B5CF6"    # violet
    },
    "confucius": {
        "name": "Confucius",
        "tradition": "Confucianism",
        "tagline": "Virtue, harmony & the way of the noble person",
        "icon": "📜",
        "color": "#DC2626"    # red
    },
    "krishna": {
        "name": "Krishna",
        "tradition": "Hinduism",
        "tagline": "Action, devotion & the eternal self",
        "icon": "🪈",
        "color": "#2563EB"    # blue
    },
    "upanishads": {
        "name": "The Upanishads",
        "tradition": "Vedanta",
        "tagline": "The ultimate reality within all things",
        "icon": "🕉️",
        "color": "#EA580C"    # orange
    },
}
