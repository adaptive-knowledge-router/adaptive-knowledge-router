ENTITY_LOOKUP_PAPER_BY_ID = """
MATCH (p:Paper {paper_id: $paper_id})
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 1
"""

ENTITY_LOOKUP_PAPER_BY_ID_COUNT = """
MATCH (p:Paper {paper_id: $paper_id})
RETURN count(p) AS total_count
"""

ENTITY_LOOKUP_PAPER_BY_TITLE = """
MATCH (p:Paper)
WHERE toLower(p.title) CONTAINS toLower($title)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 10
"""

ENTITY_LOOKUP_PAPER_BY_TITLE_COUNT = """
MATCH (p:Paper)
WHERE toLower(p.title) CONTAINS toLower($title)
RETURN count(p) AS total_count
"""

ENTITY_LOOKUP_PAPER_BY_DOI = """
MATCH (p:Paper {doi: $doi})
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 5
"""

ENTITY_LOOKUP_PAPER_BY_DOI_COUNT = """
MATCH (p:Paper {doi: $doi})
RETURN count(p) AS total_count
"""

ENTITY_LOOKUP_PAPER_BY_JOURNAL_REF = """
MATCH (p:Paper)
WHERE toLower(p.journal_ref) CONTAINS toLower($journal_ref)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 10
"""

ENTITY_LOOKUP_PAPER_BY_JOURNAL_REF_COUNT = """
MATCH (p:Paper)
WHERE toLower(p.journal_ref) CONTAINS toLower($journal_ref)
RETURN count(p) AS total_count
"""

ENTITY_LOOKUP_PAPER_BY_SUBMITTER = """
MATCH (p:Paper)
WHERE toLower(p.submitter) CONTAINS toLower($submitter)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 10
"""

ENTITY_LOOKUP_PAPER_BY_SUBMITTER_COUNT = """
MATCH (p:Paper)
WHERE toLower(p.submitter) CONTAINS toLower($submitter)
RETURN count(p) AS total_count
"""

ENTITY_LOOKUP_AUTHOR_BY_NAME = """
MATCH (a:Author)-[:WROTE]->(p:Paper)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
OPTIONAL MATCH (co:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT co.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 20
"""

ENTITY_LOOKUP_AUTHOR_BY_NAME_COUNT = """
MATCH (a:Author)-[:WROTE]->(p:Paper)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
RETURN count(DISTINCT p) AS total_count
"""

ENTITY_LOOKUP_CATEGORY_BY_NAME = """
MATCH (c:Category)<-[:IN_CATEGORY]-(p:Paper)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

ENTITY_LOOKUP_CATEGORY_BY_NAME_COUNT = """
MATCH (c:Category)<-[:IN_CATEGORY]-(p:Paper)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
RETURN count(DISTINCT p) AS total_count
"""

RELATION_FILTER_AUTHOR_TO_PAPERS = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)
OPTIONAL MATCH (co:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT co.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 20
"""


RELATION_FILTER_AUTHOR_TO_PAPERS_COUNT = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)
RETURN count(DISTINCT p) AS total_count
"""

RELATION_FILTER_CATEGORY_TO_PAPERS = """
MATCH (c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
MATCH (c)<-[:IN_CATEGORY]-(p:Paper)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_CATEGORY_TO_PAPERS_COUNT = """
MATCH (c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
MATCH (c)<-[:IN_CATEGORY]-(p:Paper)
RETURN count(DISTINCT p) AS total_count
"""

RELATION_FILTER_PAPER_TO_AUTHORS = """
MATCH (a:Author)-[:WROTE]->(p:Paper {paper_id: $paper_id})
RETURN a.author_name AS author_name
LIMIT 20
"""

RELATION_FILTER_PAPER_TO_AUTHORS_COUNT = """
MATCH (a:Author)-[:WROTE]->(p:Paper {paper_id: $paper_id})
RETURN count(a) AS total_count
"""

RELATION_FILTER_PAPER_TO_CATEGORIES = """
MATCH (p:Paper {paper_id: $paper_id})-[:IN_CATEGORY]->(c:Category)
RETURN c.category_name AS category_name
LIMIT 20
"""

RELATION_FILTER_PAPER_TO_CATEGORIES_COUNT = """
MATCH (p:Paper {paper_id: $paper_id})-[:IN_CATEGORY]->(c:Category)
RETURN count(c) AS total_count
"""

RELATION_FILTER_CATEGORY_TO_PAPERS_WITH_METADATA = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p:Paper)
WHERE ($has_doi IS NULL OR ($has_doi = true AND p.doi IS NOT NULL AND trim(p.doi) <> "") OR ($has_doi = false AND (p.doi IS NULL OR trim(p.doi) = "")))
  AND ($has_journal_ref IS NULL OR ($has_journal_ref = true AND p.journal_ref IS NOT NULL AND trim(p.journal_ref) <> "") OR ($has_journal_ref = false AND (p.journal_ref IS NULL OR trim(p.journal_ref) = "")))
  AND ($submitter IS NULL OR toLower(p.submitter) CONTAINS toLower($submitter))
  AND ($comments_contains IS NULL OR toLower(p.comments) CONTAINS toLower($comments_contains))
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_CATEGORY_TO_PAPERS_WITH_METADATA_COUNT = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p:Paper)
WHERE ($has_doi IS NULL OR ($has_doi = true AND p.doi IS NOT NULL AND trim(p.doi) <> "") OR ($has_doi = false AND (p.doi IS NULL OR trim(p.doi) = "")))
  AND ($has_journal_ref IS NULL OR ($has_journal_ref = true AND p.journal_ref IS NOT NULL AND trim(p.journal_ref) <> "") OR ($has_journal_ref = false AND (p.journal_ref IS NULL OR trim(p.journal_ref) = "")))
  AND ($submitter IS NULL OR toLower(p.submitter) CONTAINS toLower($submitter))
  AND ($comments_contains IS NULL OR toLower(p.comments) CONTAINS toLower($comments_contains))
RETURN count(DISTINCT p) AS total_count
"""

RELATION_FILTER_AUTHOR_TO_PAPERS_EXCLUDING_CATEGORY = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)
WHERE NOT EXISTS {
  MATCH (p)-[:IN_CATEGORY]->(:Category {category_name: $exclude_category_name})
}
OPTIONAL MATCH (co:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT co.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_AUTHOR_TO_PAPERS_EXCLUDING_CATEGORY_COUNT = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)
WHERE NOT EXISTS {
  MATCH (p)-[:IN_CATEGORY]->(:Category {category_name: $exclude_category_name})
}
RETURN count(DISTINCT p) AS total_count
"""


RELATION_FILTER_PAPERS_IN_ANY_OF_CATEGORIES = """
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category_name IN $category_names
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_PAPERS_IN_ANY_OF_CATEGORIES_COUNT = """
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category_name IN $category_names
RETURN count(DISTINCT p) AS total_count
"""

RELATION_FILTER_PAPERS_IN_ALL_CATEGORIES = """
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category_name IN $category_names
WITH p, collect(DISTINCT c.category_name) AS matched_categories
WHERE size(matched_categories) = size($category_names)
OPTIONAL MATCH (a:Author)-[:WROTE]->(p)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p.paper_id AS paper_id,
       p.title AS title,
       substring(p.abstract, 0, 300) AS abstract,
       p.comments AS comments,
       p.journal_ref AS journal_ref,
       p.doi AS doi,
       p.submitter AS submitter,
       p.report_no AS report_no,
       p.license AS license,
       p.update_date AS update_date,
       p.version_count AS version_count,
       p.categories_raw AS categories_raw,
       collect(DISTINCT a.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_PAPERS_IN_ALL_CATEGORIES_COUNT = """
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category_name IN $category_names
WITH p, collect(DISTINCT c.category_name) AS matched_categories
WHERE size(matched_categories) = size($category_names)
RETURN count(DISTINCT p) AS total_count
"""

MULTI_HOP_2_AUTHOR_TO_CATEGORIES = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)-[:IN_CATEGORY]->(c:Category)
RETURN DISTINCT c.category_name AS category_name
LIMIT 20
"""

MULTI_HOP_2_AUTHOR_TO_CATEGORIES_COUNT = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p:Paper)-[:IN_CATEGORY]->(c:Category)
RETURN count(DISTINCT c) AS total_count
"""

MULTI_HOP_2_CATEGORY_TO_AUTHORS = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p:Paper)<-[:WROTE]-(a:Author)
RETURN DISTINCT a.author_name AS author_name
LIMIT 20
"""

MULTI_HOP_2_CATEGORY_TO_AUTHORS_COUNT = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p:Paper)<-[:WROTE]-(a:Author)
RETURN count(DISTINCT a) AS total_count
"""

MULTI_HOP_2_PAPER_TO_OTHER_PAPERS_BY_SAME_AUTHORS = """
MATCH (a:Author)-[:WROTE]->(p1:Paper {paper_id: $paper_id})
MATCH (a)-[:WROTE]->(p2:Paper)
WHERE p1.paper_id <> p2.paper_id
OPTIONAL MATCH (a2:Author)-[:WROTE]->(p2)
OPTIONAL MATCH (p2)-[:IN_CATEGORY]->(c:Category)
RETURN DISTINCT p2.paper_id AS paper_id,
       p2.title AS title,
       substring(p2.abstract, 0, 300) AS abstract,
       p2.comments AS comments,
       p2.journal_ref AS journal_ref,
       p2.doi AS doi,
       p2.submitter AS submitter,
       p2.report_no AS report_no,
       p2.license AS license,
       p2.update_date AS update_date,
       p2.version_count AS version_count,
       p2.categories_raw AS categories_raw,
       collect(DISTINCT a2.author_name) AS authors,
       collect(DISTINCT c.category_name) AS categories
LIMIT 20
"""

MULTI_HOP_2_PAPER_TO_OTHER_PAPERS_BY_SAME_AUTHORS_COUNT = """
MATCH (a:Author)-[:WROTE]->(p1:Paper {paper_id: $paper_id})
MATCH (a)-[:WROTE]->(p2:Paper)
WHERE p1.paper_id <> p2.paper_id
RETURN count(DISTINCT p2) AS total_count
"""

MULTI_HOP_3_CO_AUTHORS_IN_CATEGORY = """
MATCH (a1:Author)
WHERE toLower(a1.author_name) CONTAINS toLower($author_name)
MATCH (a1)-[:WROTE]->(p:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
MATCH (a2)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
RETURN DISTINCT a2.author_name AS co_author
LIMIT 20
"""

MULTI_HOP_3_CO_AUTHORS_IN_CATEGORY_COUNT = """
MATCH (a1:Author)
WHERE toLower(a1.author_name) CONTAINS toLower($author_name)
MATCH (a1)-[:WROTE]->(p:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
MATCH (a2)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
RETURN count(DISTINCT a2) AS total_count
"""

MULTI_HOP_3_AUTHOR_TO_SAME_CATEGORY_PAPERS = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p1:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)
WHERE p1.paper_id <> p2.paper_id
OPTIONAL MATCH (a2:Author)-[:WROTE]->(p2)
OPTIONAL MATCH (p2)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p2.paper_id AS paper_id,
       p2.title AS title,
       substring(p2.abstract, 0, 300) AS abstract,
       p2.comments AS comments,
       p2.journal_ref AS journal_ref,
       p2.doi AS doi,
       p2.submitter AS submitter,
       p2.report_no AS report_no,
       p2.license AS license,
       p2.update_date AS update_date,
       p2.version_count AS version_count,
       p2.categories_raw AS categories_raw,
       collect(DISTINCT a2.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

MULTI_HOP_3_AUTHOR_TO_SAME_CATEGORY_PAPERS_COUNT = """
MATCH (a:Author)
WHERE toLower(a.author_name) CONTAINS toLower($author_name)
MATCH (a)-[:WROTE]->(p1:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)
WHERE p1.paper_id <> p2.paper_id
RETURN count(DISTINCT p2) AS total_count
"""

MULTI_HOP_3_CATEGORY_TO_PAPERS_BY_AUTHORS = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p1:Paper)<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)
OPTIONAL MATCH (a2:Author)-[:WROTE]->(p2)
OPTIONAL MATCH (p2)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p2.paper_id AS paper_id,
       p2.title AS title,
       substring(p2.abstract, 0, 300) AS abstract,
       p2.comments AS comments,
       p2.journal_ref AS journal_ref,
       p2.doi AS doi,
       p2.submitter AS submitter,
       p2.report_no AS report_no,
       p2.license AS license,
       p2.update_date AS update_date,
       p2.version_count AS version_count,
       p2.categories_raw AS categories_raw,
       collect(DISTINCT a2.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

MULTI_HOP_3_CATEGORY_TO_PAPERS_BY_AUTHORS_COUNT = """
MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p1:Paper)<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)
RETURN count(DISTINCT p2) AS total_count
"""

MULTI_HOP_3_PAPER_TO_AUTHORS_IN_SAME_CATEGORIES = """
MATCH (p1:Paper {paper_id: $paper_id})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)<-[:WROTE]-(a:Author)
WHERE p1.paper_id <> p2.paper_id
RETURN DISTINCT a.author_name AS author_name,
       c.category_name AS category_name
LIMIT 20
"""

MULTI_HOP_3_PAPER_TO_AUTHORS_IN_SAME_CATEGORIES_COUNT = """
MATCH (p1:Paper {paper_id: $paper_id})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)<-[:WROTE]-(a:Author)
WHERE p1.paper_id <> p2.paper_id
RETURN count(DISTINCT a) AS total_count
"""

MULTI_HOP_4_AUTHOR_TO_RELATED_AUTHORS_VIA_SHARED_CATEGORIES = """
MATCH (a1:Author)
WHERE toLower(a1.author_name) CONTAINS toLower($author_name)
MATCH (a1)-[:WROTE]->(p1:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
RETURN DISTINCT a2.author_name AS related_author,
       c.category_name AS shared_category
LIMIT 20
"""

MULTI_HOP_4_AUTHOR_TO_RELATED_AUTHORS_VIA_SHARED_CATEGORIES_COUNT = """
MATCH (a1:Author)
WHERE toLower(a1.author_name) CONTAINS toLower($author_name)
MATCH (a1)-[:WROTE]->(p1:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
RETURN count(DISTINCT a2) AS total_count
"""
MULTI_HOP_4_CATEGORY_TO_RELATED_CATEGORIES_VIA_AUTHORS = """
MATCH (c1:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p1:Paper)<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c2:Category)
WHERE c1.category_name <> c2.category_name
RETURN DISTINCT c2.category_name AS related_category
LIMIT 20
"""

MULTI_HOP_4_CATEGORY_TO_RELATED_CATEGORIES_VIA_AUTHORS_COUNT = """
MATCH (c1:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p1:Paper)<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c2:Category)
WHERE c1.category_name <> c2.category_name
RETURN count(DISTINCT c2) AS total_count
"""

MULTI_HOP_4_PAPER_TO_RELATED_PAPERS_VIA_AUTHORS_AND_CATEGORIES = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p3:Paper)
WHERE p1.paper_id <> p2.paper_id
  AND p1.paper_id <> p3.paper_id
OPTIONAL MATCH (a3:Author)-[:WROTE]->(p3)
OPTIONAL MATCH (p3)-[:IN_CATEGORY]->(c3:Category)
RETURN DISTINCT p3.paper_id AS paper_id,
       p3.title AS title,
       substring(p3.abstract, 0, 300) AS abstract,
       p3.comments AS comments,
       p3.journal_ref AS journal_ref,
       p3.doi AS doi,
       p3.submitter AS submitter,
       p3.report_no AS report_no,
       p3.license AS license,
       p3.update_date AS update_date,
       p3.version_count AS version_count,
       p3.categories_raw AS categories_raw,
       collect(DISTINCT a3.author_name) AS authors,
       collect(DISTINCT c3.category_name) AS categories
LIMIT 20
"""

MULTI_HOP_4_PAPER_TO_RELATED_PAPERS_VIA_AUTHORS_AND_CATEGORIES_COUNT = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p3:Paper)
WHERE p1.paper_id <> p2.paper_id
  AND p1.paper_id <> p3.paper_id
RETURN count(DISTINCT p3) AS total_count
"""

RELATION_FILTER_PAPER_TO_PAPERS_IN_CATEGORY = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
  AND p1.paper_id <> p2.paper_id
OPTIONAL MATCH (a2:Author)-[:WROTE]->(p2)
OPTIONAL MATCH (p2)-[:IN_CATEGORY]->(c2:Category)
RETURN DISTINCT p2.paper_id AS paper_id,
       p2.title AS title,
       substring(p2.abstract, 0, 300) AS abstract,
       p2.comments AS comments,
       p2.journal_ref AS journal_ref,
       p2.doi AS doi,
       p2.submitter AS submitter,
       p2.report_no AS report_no,
       p2.license AS license,
       p2.update_date AS update_date,
       p2.version_count AS version_count,
       p2.categories_raw AS categories_raw,
       collect(DISTINCT a2.author_name) AS authors,
       collect(DISTINCT c2.category_name) AS categories
LIMIT 20
"""

RELATION_FILTER_PAPER_TO_PAPERS_IN_CATEGORY_COUNT = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a:Author)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
  AND p1.paper_id <> p2.paper_id
RETURN count(DISTINCT p2) AS total_count
"""

MULTI_HOP_3_PAPER_TO_CO_AUTHORS_IN_CATEGORY = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a1:Author)
MATCH (a1)-[:WROTE]->(p:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
MATCH (a2)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
RETURN DISTINCT a2.author_name AS co_author
LIMIT 20
"""

MULTI_HOP_3_PAPER_TO_CO_AUTHORS_IN_CATEGORY_COUNT = """
MATCH (p1:Paper {paper_id: $paper_id})<-[:WROTE]-(a1:Author)
MATCH (a1)-[:WROTE]->(p:Paper)<-[:WROTE]-(a2:Author)
WHERE a1.author_name <> a2.author_name
MATCH (a2)-[:WROTE]->(p2:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE toLower(c.category_name) CONTAINS toLower($category_name)
RETURN count(DISTINCT a2) AS total_count
"""

PATH_EXPLAIN_AUTHOR_TO_AUTHOR_VIA_CATEGORY = """
MATCH (a1:Author)
WHERE toLower(a1.author_name) CONTAINS toLower($author1)
MATCH (a2:Author)
WHERE toLower(a2.author_name) CONTAINS toLower($author2)
MATCH (a1)-[:WROTE]->(p1:Paper)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p2:Paper)<-[:WROTE]-(a2)
RETURN a1.author_name AS author1,
       p1.title AS paper1,
       c.category_name AS connecting_category,
       p2.title AS paper2,
       a2.author_name AS author2
LIMIT 10
"""

PATH_EXPLAIN_PAPER_TO_AUTHOR = """
MATCH (p:Paper {paper_id: $paper_id})<-[:WROTE]-(a:Author)
RETURN p.paper_id AS paper_id,
       p.title AS title,
       a.author_name AS author_name
LIMIT 20
"""