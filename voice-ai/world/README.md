# World files

The course runs on one fictional lender per edition. Each folder holds the world bible and the machine-readable files that the data generator, the labs' data, the exercises and the solutions read.

| File | What it is |
|---|---|
| `WORLD.md` | The world bible: the lender, campaigns, agent, pipeline, tools, CRM, entities, personas, flows, policies, latency vocabulary and SLOs, turn-taking settings, trace schema, failure taxonomy, gold sets and judges, the incident log T01-T10, the numbers that stay consistent, program constants and the cost model |
| `constants.json` | The numbers and names code needs: field names, products, campaigns and budgets, calling windows, language groups, personas, flows, SLOs, volumes, world rates, cost model, check keywords |
| `tools.schema.json` | JSON Schema of every tool's arguments and result |
| `crm.schema.json` | JSON Schema of one row of every CRM table |
| `policies.yaml` | Policies C01-C16 with source, check type, inputs and parameters (every value is JSON, so `tools/mini_yaml.py` reads it with the standard library) |
| `phrases.json` | Utterance templates the data generator speaks from |

| Edition | Folder | Lender and agent | Language groups | Money |
|---|---|---|---|---|
| Global | `global/` | Steelyard Credit (fictional US lender), Hazel | English, Spanish-dominant, Spanglish | US dollars, integer cents |
| India | `india/` | Tarazu Finance (fictional Indian NBFC), Asha | The three groups in `india/constants.json` | Rupees, integer paise |

Ids are shared across editions: personas P01-P13, flows F01-F10, checks C01-C16, incidents T01-T10, taxonomy codes, judges J1-J3. The numbers the labs compute for the course are identical in both editions.
