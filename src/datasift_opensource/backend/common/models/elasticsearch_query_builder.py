import json

from pydantic import BaseModel, Field


class MatchPhrase(BaseModel):
    """
    Match Phrase class, Specifies a key-value pair that must match.
    """

    match_phrase: dict[str, str]


class BoolShouldQuery(BaseModel):
    """
    BoolShouldQuery : Requires at least one MatchPhrase condition to match.
    """
    should: list[MatchPhrase]


class MustQueryItem(BaseModel):
    """
    MustQueryItem: Must match the given Bool Should Query Conditions
    """
    bool: BoolShouldQuery


class BoolMustQuery(BaseModel):
    """
    BoolMustQuery: Groups multiple MustQueryItem conditions.
    """
    must: list[MustQueryItem]


class Query(BaseModel):
    """
    Defines the main query with must conditions.
    """
    bool: BoolMustQuery


class SearchRequest(BaseModel):
    """
    Represents a search request with specific fields and a query.
    """
    source: list[str] = Field(alias="_source")
    size: int = 1000
    query: Query

"""
example_search_Request : {
  "_source": [
    "entity.assets.project_id",
    "entity.assets.resource_key",
    "artifact_id"
  ],
  "query": {
    "bool": {
      "must": [
        {
          "bool": {
            "should": [
              { "match_phrase": { "entity.assets.resource_key": "||" } },
              { "match_phrase": { "entity.assets.resource_key": "0000:0000:0000:0000:0000:FFFF:092E:EBE0|19530|Default" } }
            ]
          }
        },
        {
          "bool": {
            "should": [
              { "match_phrase": { "entity.assets.project_id": "1f78a206-758a-4a46-a159-1abd161d6be5" } }
            ]
          }
        }
      ]
    }
  }
}
"""

class ElasticsearchQueryBuilder:
    """
    To Build the ElasticSearch DSL Query for the Global Search API, Search Requests
    """
    def __init__(self, source_fields: list[str] = None):
        self.source = source_fields or []
        self.must_conditions = []
        self.size : int= 1000

    def add_should_condition(self, field: str, values: list[str]):
        """
        Adds a new `should` condition inside `must`.

        Example:
        field = "entity.assets.resource_key"
        values = ["0000:0000:0000:0000:0000:FFFF:092E:EBE0|19530|Default", "||"]
        """
        should_conditions = [MatchPhrase(match_phrase={field: value}) for value in values]
        must_query_item = MustQueryItem(bool=BoolShouldQuery(should=should_conditions))
        self.must_conditions.append(must_query_item)

    def add_size(self,size: int):
        """
        Adds a size to the Elasticsearch DSL query
        :param size: size for the request query
        """
        if size:
            self.size = size

    def build(self) -> SearchRequest:
        """Builds the final Elasticsearch DSL query as a SearchRequest."""
        query_structure = SearchRequest(
            _source=self.source,
            query=Query(bool=BoolMustQuery(must=self.must_conditions)),
            size=self.size
        )
        return query_structure


# Example Usage
if __name__ == "__main__":
    builder = ElasticsearchQueryBuilder(source_fields=[
        "entity.assets.project_id",
        "entity.assets.resource_key",
        "artifact_id"
    ])

    # Add multiple `should` conditions inside `must`
    builder.add_should_condition("entity.assets.resource_key", ["||", "0000:0000:0000:0000:0000:FFFF:092E:EBE0|19530|Default"])
    builder.add_should_condition("entity.assets.project_id", ["1f78a206-758a-4a46-a159-1abd161d6be5"])

    # Generate the final query
    elasticsearch_query = builder.build()
    print(json.dumps(elasticsearch_query.model_dump(),indent=2))

