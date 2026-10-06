from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

SEARCH_ENDPOINT = "https://regen-search-veloking45.search.windows.net"
INDEX_NAME = "regen-verification-index"

credential = DefaultAzureCredential()

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=credential,
)

query = input("Enter a verification question: ")

results = search_client.search(
    search_text=query,
    top=3,
)

print("\nTop matching rules:\n")

for result in results:
    print("TITLE:", result.get("title"))
    print("ACTIVITY TYPE:", result.get("activity_type"))
    print("CONTENT:")
    print(result.get("content"))
    print("-" * 60)
