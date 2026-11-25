"""Source content for the bundled QuirkSearch corpus ("QuirkPedia").

Each article: slug, title, category, description, sections [(heading, [paragraphs])], related slugs.
`build_corpus.py` renders these into linked HTML pages under backend/corpus/.
"""

ARTICLES = [
    # ------------------------------------------------------------------ Networks
    dict(slug="http-protocol", title="HTTP: The Hypertext Transfer Protocol", category="Networks",
         description="How browsers and servers talk: requests, responses, methods, status codes and headers.",
         sections=[
             ("The request-response cycle", [
                 "HTTP is a stateless, application-layer protocol. A client opens a TCP connection to a server, sends a request line such as GET /index.html HTTP/1.1 followed by headers, and the server answers with a status line, response headers and an optional body.",
                 "Because the protocol is stateless, every request carries all the information the server needs. Cookies and tokens are layered on top to emulate sessions.",
             ]),
             ("Methods and status codes", [
                 "GET retrieves a resource, POST submits data, PUT replaces a resource and DELETE removes it. Status codes group outcomes: 2xx success, 3xx redirection, 4xx client errors such as 404 Not Found, and 5xx server errors such as 503 Service Unavailable.",
                 "Web crawlers rely on status codes to decide whether to index a page, follow a redirect or record a crawl error.",
             ]),
             ("Persistent connections", [
                 "HTTP/1.1 keeps connections alive so several requests reuse one TCP handshake. HTTP/2 multiplexes many streams over one connection, and HTTP/3 runs over QUIC on UDP to avoid head-of-line blocking.",
             ]),
         ],
         related=["tcp-ip", "dns", "rest-apis", "tls-https", "web-crawlers"]),
    dict(slug="tcp-ip", title="TCP/IP and the Transport Layer", category="Networks",
         description="Reliable byte streams over an unreliable network: handshakes, acknowledgements and congestion control.",
         sections=[
             ("Layers of the Internet", [
                 "The Internet protocol suite stacks link, internet (IP), transport (TCP and UDP) and application layers. IP delivers packets between hosts on a best-effort basis; TCP turns that into a reliable, ordered byte stream between processes identified by ports.",
             ]),
             ("The three-way handshake", [
                 "A TCP connection starts with SYN, SYN-ACK and ACK segments that synchronize sequence numbers. Every byte sent is acknowledged; lost segments are retransmitted after a timeout.",
                 "Each new connection costs at least one network round trip, which is why HTTP clients keep connection pools and reuse sockets.",
             ]),
             ("Flow and congestion control", [
                 "A sliding window prevents a fast sender from overwhelming a slow receiver, and congestion control algorithms such as slow start and CUBIC probe the available bandwidth while backing off when packets are dropped.",
             ]),
         ],
         related=["http-protocol", "osi-model", "dns", "load-balancing"]),
    dict(slug="dns", title="DNS: The Internet's Phone Book", category="Networks",
         description="How domain names are resolved to IP addresses through a hierarchy of name servers and caches.",
         sections=[
             ("Name resolution", [
                 "The Domain Name System maps human-friendly names like example.com to IP addresses. A stub resolver asks a recursive resolver, which walks the hierarchy from the root servers to the top-level domain servers and finally the authoritative name server.",
             ]),
             ("Records and caching", [
                 "Common record types include A and AAAA for addresses, CNAME for aliases, MX for mail and TXT for arbitrary text. Every answer carries a time-to-live so resolvers can cache it, which keeps DNS fast and reduces load on authoritative servers.",
                 "A crawler that visits thousands of URLs on the same host benefits enormously from DNS caching and connection reuse.",
             ]),
         ],
         related=["tcp-ip", "http-protocol", "cdn"]),
    dict(slug="tls-https", title="TLS and HTTPS", category="Networks",
         description="Encryption, certificates and the TLS handshake that secures the web.",
         sections=[
             ("Why HTTPS", [
                 "HTTPS is HTTP carried inside a Transport Layer Security session. TLS provides confidentiality through encryption, integrity through message authentication codes, and authenticity through certificates signed by trusted certificate authorities.",
             ]),
             ("The handshake", [
                 "In TLS 1.3 the client and server agree on keys using ephemeral Diffie-Hellman in a single round trip. Session resumption lets returning clients skip most of that cost.",
             ]),
         ],
         related=["http-protocol", "tcp-ip"]),
    dict(slug="rest-apis", title="Designing REST APIs", category="Networks",
         description="Resources, verbs, status codes and JSON: principles for clean HTTP APIs.",
         sections=[
             ("Resources and representations", [
                 "Representational State Transfer models a system as resources identified by URLs. Clients manipulate them with standard HTTP methods and exchange representations, typically JSON documents.",
                 "A search engine API might expose GET /api/search?q=database for queries, GET /api/stats for analytics and POST /api/crawl to start a crawl job.",
             ]),
             ("Good practices", [
                 "Validate input and return precise status codes: 400 or 422 for invalid parameters, 404 for missing resources, 409 for conflicts and 429 when a client exceeds a rate limit. Keep endpoints stateless so they scale horizontally behind a load balancer.",
             ]),
         ],
         related=["http-protocol", "rate-limiting", "load-balancing"]),
    dict(slug="rate-limiting", title="Rate Limiting and Politeness", category="Networks",
         description="Token buckets, sliding windows and crawl delays that protect servers from overload.",
         sections=[
             ("Why limit request rates", [
                 "Servers have finite capacity. Rate limiting caps how many requests a client may send in a time window, protecting availability and ensuring fair use.",
             ]),
             ("Algorithms", [
                 "The token bucket algorithm adds tokens at a fixed rate and spends one per request, allowing short bursts. A fixed delay between requests to the same host is the simplest scheme and is what polite web crawlers use, often honoring the Crawl-delay directive from robots.txt.",
             ]),
         ],
         related=["web-crawlers", "robots-txt", "rest-apis"]),
    dict(slug="web-crawlers", title="How Web Crawlers Work", category="Search",
         description="Frontiers, graph traversal, politeness and duplicate detection inside a web spider.",
         sections=[
             ("The crawl loop", [
                 "A web crawler starts from seed URLs, downloads each page, extracts its links and adds unseen links to a frontier queue. Processing the frontier in first-in first-out order produces a breadth-first traversal of the web graph.",
                 "A visited set, usually a hash set of normalized URLs, guarantees each page is fetched once even when thousands of pages link to it.",
             ]),
             ("Politeness and robustness", [
                 "Responsible crawlers respect robots.txt, limit their request rate per host, set timeouts and identify themselves with a descriptive User-Agent. They must survive DNS failures, refused connections, redirects and malformed HTML.",
             ]),
             ("Duplicate content", [
                 "Different URLs often serve identical content. Hashing the normalized text of each page with a function such as SHA-256 detects exact duplicates in constant time.",
             ]),
         ],
         related=["graph-traversal", "robots-txt", "rate-limiting", "hash-tables", "inverted-index"]),
    dict(slug="robots-txt", title="The robots.txt Standard", category="Search",
         description="The Robots Exclusion Protocol tells crawlers which paths they may visit.",
         sections=[
             ("Syntax", [
                 "A robots.txt file lives at the root of a host. It contains groups that start with a User-agent line followed by Allow and Disallow rules for path prefixes. RFC 9309 standardized the format in 2022.",
             ]),
             ("Semantics", [
                 "If robots.txt returns a 4xx status the crawler may access everything; if the server is unreachable or returns 5xx the crawler should assume everything is disallowed.",
             ]),
         ],
         related=["web-crawlers", "rate-limiting"]),
    dict(slug="osi-model", title="The OSI Reference Model", category="Networks",
         description="Seven layers from physical signals to applications, and how they map onto TCP/IP.",
         sections=[
             ("Seven layers", [
                 "The Open Systems Interconnection model describes networking as physical, data link, network, transport, session, presentation and application layers. Each layer offers services to the layer above and hides the details below.",
                 "In practice the Internet uses the simpler four-layer TCP/IP model, but the OSI vocabulary such as layer 4 load balancing or layer 7 routing remains common.",
             ]),
         ],
         related=["tcp-ip", "http-protocol"]),
    dict(slug="load-balancing", title="Load Balancing", category="Networks",
         description="Spreading traffic across servers with round robin, least connections and consistent hashing.",
         sections=[
             ("Strategies", [
                 "Load balancers distribute incoming requests over a pool of servers. Round robin cycles through servers, least connections picks the least busy one, and consistent hashing keeps a given key on the same server even as servers join or leave.",
                 "Health checks remove failing servers from rotation, improving availability.",
             ]),
         ],
         related=["rest-apis", "cdn", "hash-tables"]),
    dict(slug="cdn", title="Content Delivery Networks", category="Networks",
         description="Caching content at the network edge to cut latency for users worldwide.",
         sections=[
             ("Edge caching", [
                 "A content delivery network stores copies of static assets in data centers close to users. DNS-based or anycast routing sends each user to a nearby edge server, reducing round-trip latency and offloading the origin server.",
             ]),
         ],
         related=["dns", "load-balancing", "http-protocol"]),
    # ------------------------------------------------------------------ Databases
    dict(slug="relational-databases", title="Relational Databases", category="Databases",
         description="Tables, keys and relations: the model behind SQL database management systems.",
         sections=[
             ("The relational model", [
                 "Edgar Codd proposed the relational model in 1970. Data lives in relations, or tables, made of rows and columns. A primary key uniquely identifies each row, and a foreign key references the primary key of another table, expressing relationships.",
             ]),
             ("Why it endures", [
                 "Declarative SQL queries, strong consistency through transactions, and decades of query optimizer research make relational database management systems the default choice for structured data.",
             ]),
         ],
         related=["sql-basics", "normalization", "transactions-acid", "sqlite"]),
    dict(slug="sql-basics", title="SQL Basics", category="Databases",
         description="SELECT, JOIN, GROUP BY and friends: querying relational data with SQL.",
         sections=[
             ("Querying", [
                 "SELECT chooses columns, FROM names tables, WHERE filters rows, JOIN combines tables on matching keys, GROUP BY aggregates and ORDER BY sorts. For example, a search engine can count postings per document with SELECT doc_id, COUNT(*) FROM postings GROUP BY doc_id.",
             ]),
             ("Modifying data", [
                 "INSERT adds rows, UPDATE changes them and DELETE removes them. Upserts such as INSERT ... ON CONFLICT DO UPDATE combine insert and update in one atomic statement.",
             ]),
         ],
         related=["relational-databases", "indexing-btrees", "query-optimization"]),
    dict(slug="normalization", title="Database Normalization", category="Databases",
         description="First, second and third normal form: removing redundancy and update anomalies.",
         sections=[
             ("Normal forms", [
                 "Normalization organizes tables so each fact is stored once. First normal form requires atomic column values, second normal form removes partial dependencies on a composite key, and third normal form removes transitive dependencies between non-key columns.",
             ]),
             ("Trade-offs", [
                 "A normalized schema avoids insertion, update and deletion anomalies. Read-heavy systems sometimes denormalize selected data, such as caching a document frequency, to save joins.",
             ]),
         ],
         related=["relational-databases", "sql-basics"]),
    dict(slug="indexing-btrees", title="Database Indexes and B-Trees", category="Databases",
         description="Why indexes make lookups logarithmic and how B-trees keep them balanced.",
         sections=[
             ("B-tree indexes", [
                 "A B-tree is a balanced search tree with high fan-out. Because each node holds many keys, the tree stays shallow and a lookup touches only a few disk pages: O(log n) instead of a full table scan.",
                 "Most relational databases, including SQLite and PostgreSQL, implement primary keys and secondary indexes as B-trees or B+ trees.",
             ]),
             ("Choosing indexes", [
                 "Index the columns used in WHERE clauses and joins. Composite indexes serve queries that filter on their leftmost columns. Every index speeds reads but slows writes, so index deliberately.",
             ]),
         ],
         related=["query-optimization", "binary-search", "sql-basics"]),
    dict(slug="transactions-acid", title="Transactions and ACID", category="Databases",
         description="Atomicity, consistency, isolation and durability keep data correct under failures.",
         sections=[
             ("ACID properties", [
                 "A transaction groups operations into one unit. Atomicity means all or nothing, consistency preserves integrity constraints, isolation hides concurrent transactions from each other, and durability guarantees committed data survives crashes.",
             ]),
             ("Write-ahead logging", [
                 "Databases achieve durability and atomicity by writing changes to a log before applying them. SQLite's WAL mode lets readers continue while a writer appends to the log.",
                 "An indexer should insert a document and all its postings in a single transaction so a crash never leaves a half-indexed page.",
             ]),
         ],
         related=["relational-databases", "sqlite", "postgresql"]),
    dict(slug="query-optimization", title="Query Optimization", category="Databases",
         description="How a database planner chooses join orders and access paths using statistics.",
         sections=[
             ("The query planner", [
                 "SQL is declarative: the database decides how to execute a query. The optimizer enumerates plans, estimates their cost using table statistics and picks the cheapest, choosing between index lookups and scans and between nested-loop, hash and merge joins.",
                 "EXPLAIN QUERY PLAN in SQLite reveals whether a query uses an index.",
             ]),
         ],
         related=["indexing-btrees", "sql-basics", "hash-tables"]),
    dict(slug="sqlite", title="SQLite", category="Databases",
         description="The embedded, serverless SQL database engine that ships inside billions of devices.",
         sections=[
             ("Embedded by design", [
                 "SQLite stores a whole database in a single file and runs inside the application process, with no server to configure. It supports transactions, foreign keys, indexes, triggers and window functions.",
             ]),
             ("When to use it", [
                 "SQLite is ideal for local applications, prototypes, testing and read-heavy workloads. High write concurrency from many clients is better served by a client-server database such as PostgreSQL.",
             ]),
         ],
         related=["relational-databases", "postgresql", "transactions-acid"]),
    dict(slug="postgresql", title="PostgreSQL", category="Databases",
         description="A powerful open-source object-relational database with MVCC and rich indexing.",
         sections=[
             ("Features", [
                 "PostgreSQL offers multi-version concurrency control, a sophisticated cost-based planner, many index types such as B-tree, hash, GIN and GiST, and built-in full-text search with tsvector and tsquery.",
             ]),
         ],
         related=["sqlite", "relational-databases", "inverted-index"]),
    dict(slug="nosql", title="NoSQL Databases", category="Databases",
         description="Key-value, document, column and graph stores and the trade-offs they make.",
         sections=[
             ("Families", [
                 "Key-value stores such as Redis act like a distributed hash table. Document databases store JSON-like documents, wide-column stores such as Cassandra partition data across nodes, and graph databases model relationships directly.",
                 "Many NoSQL systems relax consistency for availability and partition tolerance, as described by the CAP theorem.",
             ]),
         ],
         related=["relational-databases", "hash-tables"]),
    # ------------------------------------------------------------------ Algorithms
    dict(slug="hash-tables", title="Hash Tables", category="Algorithms",
         description="Constant-time lookups with hash functions, buckets and collision resolution.",
         sections=[
             ("How hashing works", [
                 "A hash table maps keys to values by computing a hash function that turns a key into an array index. With a good hash function and a bounded load factor, insertion, deletion and lookup run in expected O(1) time.",
             ]),
             ("Collisions", [
                 "Two keys may hash to the same slot. Separate chaining stores colliding entries in a list per bucket, while open addressing probes for another empty slot. Python dictionaries use open addressing.",
                 "Search engines use hash maps for the inverted index dictionary, mapping each term to its postings list.",
             ]),
         ],
         related=["inverted-index", "tries", "big-o"]),
    dict(slug="tries", title="Tries and Prefix Trees", category="Algorithms",
         description="Tree structures keyed by characters that power autocomplete and prefix search.",
         sections=[
             ("Structure", [
                 "A trie stores strings character by character: each edge is labelled with a character and each path from the root spells a prefix. Looking up a prefix of length m takes O(m) time regardless of how many words are stored.",
             ]),
             ("Autocomplete", [
                 "To suggest completions, walk down to the node for the typed prefix and collect the words beneath it, ranking them by frequency. Search boxes use this to offer suggestions as the user types.",
             ]),
         ],
         related=["autocomplete", "hash-tables", "heaps-priority-queues"]),
    dict(slug="heaps-priority-queues", title="Heaps and Priority Queues", category="Algorithms",
         description="Binary heaps give O(log n) insert and extract-min, perfect for top-k selection.",
         sections=[
             ("Binary heaps", [
                 "A binary heap is a complete binary tree stored in an array where every parent is ordered relative to its children. Insertion and removal of the minimum take O(log n) time.",
             ]),
             ("Top-k selection", [
                 "To find the k highest scores among n items, keep a min-heap of size k: push each item and pop the smallest whenever the heap exceeds k. This costs O(n log k), far cheaper than sorting everything when k is small. Search engines use exactly this to return the top ten results.",
             ]),
         ],
         related=["sorting-algorithms", "bm25", "big-o"]),
    dict(slug="graph-traversal", title="Graph Traversal: BFS and DFS", category="Algorithms",
         description="Breadth-first and depth-first search for exploring vertices and edges.",
         sections=[
             ("Breadth-first search", [
                 "BFS explores a graph level by level using a FIFO queue. It visits all vertices at distance one before distance two, finds shortest paths in unweighted graphs and runs in O(V + E) time.",
             ]),
             ("Depth-first search", [
                 "DFS follows one path as deep as possible before backtracking, using a stack or recursion. It is useful for topological sorting and cycle detection.",
                 "Web crawlers usually prefer BFS because important pages tend to be close to the seeds.",
             ]),
         ],
         related=["web-crawlers", "pagerank", "big-o"]),
    dict(slug="sorting-algorithms", title="Sorting Algorithms", category="Algorithms",
         description="Quicksort, mergesort, heapsort and Timsort compared.",
         sections=[
             ("Comparison sorts", [
                 "Mergesort guarantees O(n log n) and is stable, quicksort is fast in practice with O(n log n) expected time, and heapsort sorts in place in O(n log n). No comparison sort can beat O(n log n) in the worst case.",
                 "Python and Java use Timsort, a hybrid of mergesort and insertion sort that exploits existing runs in real data.",
             ]),
         ],
         related=["heaps-priority-queues", "big-o", "binary-search"]),
    dict(slug="binary-search", title="Binary Search", category="Algorithms",
         description="Halving the search space to find items in sorted arrays in logarithmic time.",
         sections=[
             ("The algorithm", [
                 "Binary search compares the target with the middle element of a sorted array and discards the half that cannot contain it. It needs at most about log2(n) comparisons, so a million sorted items need only twenty steps.",
             ]),
         ],
         related=["indexing-btrees", "sorting-algorithms", "big-o"]),
    dict(slug="big-o", title="Big-O Notation and Complexity", category="Algorithms",
         description="Describing how running time and memory grow with input size.",
         sections=[
             ("Asymptotic analysis", [
                 "Big-O notation gives an upper bound on growth: O(1) constant, O(log n) logarithmic, O(n) linear, O(n log n) linearithmic and O(n squared) quadratic. It lets engineers compare algorithms independently of hardware.",
                 "An inverted index turns a linear scan over every document into a lookup proportional to the number of matching postings.",
             ]),
         ],
         related=["hash-tables", "sorting-algorithms", "inverted-index"]),
    # ------------------------------------------------------------------ Search / IR
    dict(slug="inverted-index", title="The Inverted Index", category="Search",
         description="The core data structure of search engines: a map from each term to the documents containing it.",
         sections=[
             ("From documents to terms", [
                 "A forward index lists the words in each document. An inverted index flips this around: for every term it stores a postings list of the documents that contain it, often with the term frequency and positions.",
                 "To answer a query, the engine looks up each query term and merges the postings lists instead of scanning every document, which makes search fast even over millions of pages.",
             ]),
             ("Statistics", [
                 "The document frequency of a term is the length of its postings list. Ranking functions such as TF-IDF and BM25 use document frequency to reward rare, discriminative terms.",
             ]),
         ],
         related=["tf-idf", "bm25", "tokenization", "hash-tables", "postgresql"]),
    dict(slug="tf-idf", title="TF-IDF Weighting", category="Search",
         description="Term frequency times inverse document frequency: a classic relevance signal.",
         sections=[
             ("The formula", [
                 "TF-IDF multiplies how often a term appears in a document by the logarithm of the total number of documents divided by the number of documents containing the term. Frequent words in a document matter, but words that appear everywhere matter little.",
             ]),
             ("Limitations", [
                 "Raw term frequency grows without bound and long documents are favoured. BM25 fixes both problems with term frequency saturation and length normalization.",
             ]),
         ],
         related=["bm25", "inverted-index", "stop-words"]),
    dict(slug="bm25", title="BM25 Ranking Function", category="Search",
         description="Okapi BM25 scores documents with saturating term frequency and length normalization.",
         sections=[
             ("Scoring", [
                 "BM25 sums, over the query terms, the inverse document frequency of the term multiplied by a saturating function of term frequency: tf times (k1 + 1) divided by tf plus k1 times (1 minus b plus b times document length over average document length).",
                 "Typical parameters are k1 between 1.2 and 2.0 and b equal to 0.75. The parameter k1 controls how quickly repeated occurrences stop adding score, and b controls how strongly long documents are penalised.",
             ]),
             ("In practice", [
                 "BM25 remains a strong baseline and is the default ranking function in Lucene, Elasticsearch and many other search engines.",
             ]),
         ],
         related=["tf-idf", "inverted-index", "heaps-priority-queues"]),
    dict(slug="tokenization", title="Tokenization", category="Search",
         description="Splitting text into searchable tokens: lowercasing, punctuation and Unicode.",
         sections=[
             ("Breaking text apart", [
                 "Tokenization splits raw text into tokens, usually words. A simple tokenizer lowercases text, removes punctuation and splits on whitespace, while real systems also handle hyphens, apostrophes, numbers and Unicode letters.",
                 "The same analyzer must process documents at indexing time and queries at search time, otherwise query terms would never match indexed terms.",
             ]),
         ],
         related=["stemming", "stop-words", "inverted-index"]),
    dict(slug="stemming", title="Stemming and the Porter Algorithm", category="Search",
         description="Reducing words like connected, connecting and connection to a common stem.",
         sections=[
             ("Why stem", [
                 "Stemming maps morphological variants to a common root so a query for running also matches run and runs. Martin Porter published his suffix-stripping algorithm in 1980 and it is still widely used.",
             ]),
             ("How Porter works", [
                 "The algorithm measures the number of vowel-consonant sequences in a word and applies five steps of suffix rules, for example turning caresses into caress, ponies into poni and relational into relat.",
             ]),
         ],
         related=["tokenization", "stop-words"]),
    dict(slug="stop-words", title="Stop Words", category="Search",
         description="Very common words such as the, and and of that carry little meaning for retrieval.",
         sections=[
             ("Removing noise", [
                 "Stop words appear in almost every document, so their inverse document frequency is near zero and they inflate the index. Removing them shrinks postings lists and speeds up queries.",
                 "Phrase search is the exception: a query like to be or not to be consists entirely of stop words.",
             ]),
         ],
         related=["tokenization", "tf-idf"]),
    dict(slug="pagerank", title="PageRank and Link Analysis", category="Search",
         description="Ranking pages by the structure of the link graph using a random surfer model.",
         sections=[
             ("The random surfer", [
                 "PageRank models a surfer who follows random links and occasionally jumps to a random page. A page's rank is the probability of finding the surfer there, so pages linked from many important pages rank higher.",
                 "It is computed by power iteration over the link graph collected by the crawler.",
             ]),
         ],
         related=["graph-traversal", "web-crawlers", "search-engine-history"]),
    dict(slug="autocomplete", title="Search Autocomplete", category="Search",
         description="Suggesting queries as you type with prefix trees and popularity ranking.",
         sections=[
             ("Suggestions", [
                 "Autocomplete predicts what the user is typing. A trie over the vocabulary and past queries returns all completions of the current prefix, and a priority queue keeps the most popular few.",
             ]),
         ],
         related=["tries", "heaps-priority-queues"]),
    dict(slug="search-engine-history", title="A Short History of Search Engines", category="Search",
         description="From Archie and AltaVista to modern web search.",
         sections=[
             ("Early days", [
                 "Archie indexed FTP file listings in 1990. WebCrawler, launched in 1994, was among the first to index the full text of web pages, and AltaVista impressed users with speed over a large index.",
                 "Later engines combined text relevance with link analysis such as PageRank to fight spam and surface authoritative pages.",
             ]),
         ],
         related=["web-crawlers", "pagerank", "inverted-index"]),
    # ------------------------------------------------------------------ Curiosities
    dict(slug="octopus-intelligence", title="The Curious Intelligence of Octopuses", category="Curiosities",
         description="Distributed brains, camouflage and problem solving in eight-armed cephalopods.",
         sections=[
             ("A distributed nervous system", [
                 "An octopus has around five hundred million neurons, and two thirds of them live in its arms. Each arm can taste, touch and react somewhat independently of the central brain.",
                 "Octopuses open jars, escape aquarium tanks and use coconut shells as portable shelters, behaviours that suggest planning and tool use.",
             ]),
         ],
         related=["sourdough-science", "black-holes"]),
    dict(slug="sourdough-science", title="The Science of Sourdough", category="Curiosities",
         description="Wild yeast, lactic acid bacteria and fermentation in a jar of flour and water.",
         sections=[
             ("A living culture", [
                 "A sourdough starter is a symbiotic culture of wild yeast and lactic acid bacteria. The yeast produces carbon dioxide that leavens the bread, while the bacteria produce lactic and acetic acids that give the tangy flavour.",
                 "Temperature controls the balance: warmer fermentation favours mild lactic acid, cooler fermentation favours sharper acetic acid.",
             ]),
         ],
         related=["octopus-intelligence"]),
    dict(slug="black-holes", title="Black Holes Explained", category="Curiosities",
         description="Event horizons, Hawking radiation and the first image of a black hole.",
         sections=[
             ("Gravity's extreme", [
                 "A black hole is a region where gravity is so strong that nothing, not even light, can escape once it crosses the event horizon. Stellar black holes form when massive stars collapse; supermassive ones sit at the centres of galaxies.",
                 "In 2019 the Event Horizon Telescope, a planet-sized network of radio telescopes, produced the first image of a black hole's shadow in the galaxy M87.",
             ]),
         ],
         related=["octopus-intelligence"]),
]
