from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
)
from azure.search.documents import SearchClient

SEARCH_ENDPOINT = "https://regen-search-veloking45.search.windows.net"

INDEX_NAME = "regen-verification-index"

RULES_FILE = "data/regen_verification_rules.md"

credential = DefaultAzureCredential()

# -----------------------------
# 1. Create search index
# -----------------------------

index_client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=credential,
)

fields = [
    SimpleField(
        name="id",
        type=SearchFieldDataType.String,
        key=True,
    ),
    SearchableField(
        name="title",
        type=SearchFieldDataType.String,
    ),
    SearchableField(
        name="content",
        type=SearchFieldDataType.String,
    ),
    SearchableField(
        name="activity_type",
        type=SearchFieldDataType.String,
        filterable=True,
    ),
]

index = SearchIndex(
    name=INDEX_NAME,
    fields=fields,
)

try:
    index_client.create_index(index)
    print(f"Created index: {INDEX_NAME}")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index already exists: {INDEX_NAME}")
    else:
        raise


# -----------------------------
# 2. Read verification rules
# -----------------------------

with open(RULES_FILE, "r", encoding="utf-8") as f:
    rules_text = f.read()


# -----------------------------
# 3. Split rules into sections
# -----------------------------

sections = []

current_title = None
current_content = []

for line in rules_text.splitlines():

    if line.startswith("## "):

        if current_title:
            sections.append(
                {
                    "title": current_title,
                    "content": "\n".join(current_content).strip(),
                }
            )

        current_title = line.replace("## ", "").strip()
        current_content = []

    else:
        current_content.append(line)

if current_title:
    sections.append(
        {
            "title": current_title,
            "content": "\n".join(current_content).strip(),
        }
    )


# -----------------------------
# 4. Convert sections to docs
# -----------------------------

documents = []

for i, section in enumerate(sections, start=1):

    title_lower = section["title"].lower()

    if "tree planting" in title_lower:
        activity_type = "tree_planting"

    elif "seedling production" in title_lower:
        activity_type = "seedling_production"

    elif "nursery maintenance" in title_lower:
        activity_type = "nursery_maintenance"

    elif "site preparation" in title_lower:
        activity_type = "site_preparation"

    elif "human verification" in title_lower:
        activity_type = "human_verification"

    elif "green merit" in title_lower:
        activity_type = "green_merit"

    else:
        activity_type = "general"

    documents.append(
        {
            "id": str(i),
            "title": section["title"],
            "content": section["content"],
            "activity_type": activity_type,
        }
    )


# -----------------------------
# 5. Upload documents
# -----------------------------

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=credential,
)

result = search_client.upload_documents(documents=documents)

for r in result:
    print(
        f"Document {r.key}: "
        f"{'uploaded' if r.succeeded else 'FAILED'}"
    )


print("\nKnowledge index provisioning complete.")
print("Search endpoint:", SEARCH_ENDPOINT)
print("Index:", INDEX_NAME)
