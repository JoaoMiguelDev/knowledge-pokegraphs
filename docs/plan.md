# 📋 Planejamento do Projeto — Knowledge PokéGraphs

**Disciplina:** Algoritmos e Estrutura de Dados
**Entrega:** 03 de dezembro (dupla)
**Linguagem:** Python 3.10+
**Fonte de dados:** [PokéAPI v2](https://pokeapi.co/api/v2)

---

## 1. Visão geral

Construir um **Knowledge Graph** do universo Pokémon cobrindo a **Geração 1 + satélites cross-gen** (Pokémon de outras gerações necessários para fechar cadeias evolutivas). O grafo será:

- **Coletado** via consumo da PokéAPI com cache local em disco;
- **Curado** em um arquivo `kg.json` segundo uma ontologia explícita;
- **Manipulado** por uma classe `KnowledgeGraph` implementada do zero (lista de adjacência);
- **Consultado** por uma demo interativa (menu no terminal);
- **Visualizado** por projeções geradas com `networkx` + `matplotlib`.

**Princípio de arquitetura:** o pipeline roda **offline na apresentação**. A demo nunca toca a rede.

```
PokéAPI  ──fetch.py──▶  cache/  ──build_kg.py──▶  kg.json  ──main.py──▶  demo
                                    │
                                    └──▶ visualizar.py ──▶ figuras (.png)
```

---

## 2. Escopo e ontologia

### 2.1 Nós

| Tipo | Origem | Propriedades |
|---|---|---|
| `Pokemon` | `/pokemon/{id}`, `/pokemon-species/{id}` | `dex_number`, `generation`, `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`, `speed` |
| `Type` | `/type/{1..18}` | `name` |
| `Ability` | `/ability/{id}` | `name` |

### 2.2 Arestas

| Origem → Destino | Predicado | Propriedades da aresta |
|---|---|---|
| `Pokemon` → `Type` | `has_type` | — |
| `Pokemon` → `Ability` | `has_ability` | `is_hidden: bool`, `slot: int` |
| `Pokemon` → `Pokemon` | `evolves_to` | `trigger` (opcional) |
| `Type` → `Type` | `double_damage_to` | `multiplier: 2.0` |
| `Type` → `Type` | `half_damage_to` | `multiplier: 0.5` |
| `Type` → `Type` | `no_damage_to` | `multiplier: 0.0` |

**Regra de normalização:** armazenar apenas as arestas do type chart na direção **atacante → defensor**. As relações inversas são derivadas por `incoming_edges()`.

**Campo avaliado e excluído (documentar no relatório):** `egg_group` — fora do escopo combate/identidade.

### 2.3 Conjunto de Pokémon

- Base: **151 Pokémon da Gen 1**.
- Satélites: Pokémon de outras gerações que **fecham** cadeias iniciadas na Gen 1 (ex.: Crobat, Steelix, Espeon, Umbreon, Pichu, Blissey, Scizor, Kingdra, Bellossom, Slowking, Magby, Elekid, Smoochum, Igglybuff, Cleffa, Porygon2, Politoed, Mime Jr. etc.).
- Estimativa final: **~175 nós `Pokemon`** + **18 `Type`** + **~80 `Ability`** ≈ **~270 nós** e **~750 arestas**.

---

## 3. Estrutura de arquivos do repositório

```
knowledge-pokegraphs/
├── README.md
├── requirements.txt          # requests, networkx, matplotlib
├── fetch.py                  # etapa 1: coleta com cache
├── build_kg.py               # etapa 2: transforma cache → kg.json
├── kg.py                     # classe KnowledgeGraph (núcleo)
├── main.py                   # demo com menu
├── visualizar.py             # gera projeções .png
├── data/
│   ├── cache/                # JSONs brutos da PokéAPI
│   ├── kg.json               # grafo curado (produto final)
│   └── log_fetch.txt         # evidência de execução real
├── figuras/                  # .png para relatório e slides
└── relatorio.md              # relatório de até 3 páginas
```

---

## 4. Fases do projeto

### 🔹 Fase 1 — Coleta (`fetch.py`)

**Objetivo:** baixar os dados brutos e salvar em `data/cache/`, com log de execução.

Tarefas:

- [ ] Implementar `fetch(endpoint)` com **cache em disco** e `time.sleep(0.1)` entre requisições.
- [ ] Implementar `id_from_url(url)` para extrair IDs sem chamadas extras.
- [ ] Baixar os **18 tipos** via `/type/1` … `/type/18`.
- [ ] Baixar os **151 Pokémon** da Gen 1 (`/pokemon/{id}` + `/pokemon-species/{id}`).
- [ ] Para cada cadeia evolutiva referenciada, baixar `/evolution-chain/{id}` **uma única vez** e identificar os satélites cross-gen.
- [ ] Baixar os satélites encontrados (pokemon + species).
- [ ] Baixar as **habilidades** referenciadas (deduplicadas).
- [ ] Gravar `data/log_fetch.txt` com timestamp, contagem de requisições e de cache hits.

**Critério de conclusão:** rodar `fetch.py` duas vezes seguidas — a segunda execução faz **zero requisições** (tudo em cache).

---

### 🔹 Fase 2 — Curadoria (`build_kg.py`)

**Objetivo:** transformar o cache bruto em `data/kg.json` seguindo a ontologia da seção 2.

Tarefas:

- [ ] Definir a **ontologia em código** (`SCHEMA`): tipos de nó permitidos e predicados válidos entre eles.
- [ ] Escrever extratores:
  - [ ] `extrair_pokemon(raw)` → nó com stats, `dex_number`, `generation`.
  - [ ] `extrair_tipos(raw)` → arestas `has_type`.
  - [ ] `extrair_habilidades(raw)` → arestas `has_ability` com `is_hidden` e `slot`.
  - [ ] `extrair_evolucoes(chain_raw)` → arestas `evolves_to`.
  - [ ] `extrair_type_chart(type_raw)` → arestas com `multiplier` (usar o mapa `double/half/no_damage_to`).
- [ ] Montar o grafo curado e **validar** contra o `SCHEMA` (rejeitar predicados inválidos).
- [ ] Escrever `data/kg.json` no formato:

```json
{
  "nodes": [
    {"id": "charizard", "type": "Pokemon",
     "properties": {"dex_number": 6, "generation": 1,
                    "hp": 78, "attack": 84, "defense": 78,
                    "sp_attack": 109, "sp_defense": 85, "speed": 100}}
  ],
  "edges": [
    {"source": "charizard", "relation": "has_type", "target": "fire", "properties": {}},
    {"source": "fire", "relation": "double_damage_to", "target": "grass", "properties": {"multiplier": 2.0}}
  ]
}
```

- [ ] Imprimir relatório de build: contagem por tipo de nó, por predicado, nós isolados (grau 0), arestas duplicadas.

**Critério de conclusão:** `kg.json` passa na validação; contagens batem com a estimativa da seção 2.3; nenhum nó isolado inesperado.

---

### 🔹 Fase 3 — Núcleo (`kg.py`)

**Objetivo:** implementar a estrutura de dados e as operações do grafo.

Tarefas:

- [ ] Classe `KnowledgeGraph` com:
  - [ ] `nodes: dict[id → {type, properties}]`
  - [ ] `adj: dict[origem → dict[relação → dict[destino → properties]]]`
- [ ] Operações obrigatórias (especificação):
  - [ ] `add_node(id, type, **props)`
  - [ ] `add_edge(source, relation, target, **props)`
  - [ ] `remove_node(id)` — **cascatear** remoção de arestas de entrada e saída.
  - [ ] `remove_edge(source, relation, target)`
  - [ ] `get_node(id)`
  - [ ] `get_neighbors(id, relation=None)`
  - [ ] `get_incoming(id, relation=None)`
- [ ] Operações extras (diferenciais):
  - [ ] `query(source=None, relation=None, target=None)` — padrão de tripla com curingas (analogia SPARQL).
  - [ ] `find_path(origem, destino)` — **BFS** (usado nas cadeias evolutivas).
  - [ ] `describe(id)` — nó + todas as arestas de entrada e saída.
  - [ ] `validate(SCHEMA)` — checagem de ontologia.
  - [ ] `load_from_json(path)` / `save_to_json(path)`.
- [ ] Documentar **complexidade** de cada operação (para o relatório).

**Critério de conclusão:** testes manuais no REPL demonstram cada operação; `find_path` conecta qualquer inicial à sua forma final.

---

### 🔹 Fase 4 — Demo (`main.py`)

**Objetivo:** menu interativo que roda offline a partir de `kg.json`.

Consultas a implementar (cada uma mapeia para um conceito da disciplina):

| # | Consulta | Conceito |
|---|---|---|
| 1 | `describe <pokemon>` | percurso de vizinhança |
| 2 | Caminho evolutivo entre dois Pokémon | BFS |
| 3 | Tipo mais efetivo contra um Pokémon (tipo duplo) | produto de multiplicadores |
| 4 | Top 5 por stat (ex.: velocidade) | ordenação sobre propriedade |
| 5 | Pokémon que compartilham tipo **e** habilidade | interseção de vizinhanças |
| 6 | Arestas `no_damage_to` (imunidades) | filtro por predicado |
| 7 | Adicionar / remover nó em tempo real | operações de escrita |

**Critério de conclusão:** demo roda em menos de 2s após o load, com respostas corretas para casos conhecidos (ex.: Rock contra Charizard = 4.0).

---

### 🔹 Fase 5 — Visualização (`visualizar.py`)

**Objetivo:** gerar as figuras para relatório e slides, **por projeções** (não reduzir o grafo).

Tarefas:

- [ ] **Projeção de tipos**: 18 nós + arestas do type chart. Cor por multiplicador.
- [ ] **Projeção evolutiva**: só `evolves_to` (floresta de cadeias).
- [ ] **Projeção de habilidades**: subgrafo de um cluster (ex.: Levitate, Sturdy).
- [ ] **Grafo completo**: cor por tipo de nó, tamanho por grau, `spring_layout` com `seed` fixa.
- [ ] Salvar em `figuras/*.png` com `dpi=200`.

**Critério de conclusão:** 4 figuras legíveis; grafo completo é apresentável como "visão geral", projeções como "leituras".

---

### 🔹 Fase 6 — Relatório e apresentação

**Relatório (≤ 3 páginas):**

- [ ] Aplicação escolhida e motivação (franquia, riqueza de relações).
- [ ] Ontologia (tabela da seção 2) e justificativa das escolhas.
- [ ] Base criada: contagens, projeções, exemplos de triplas.
- [ ] Pipeline: cache, offline-first, por que não rodar fetch na demo.
- [ ] Potenciais de aplicação dos KGs (busca semântica, recomendação, etc.).
- [ ] Limitações: tipagem contemporânea ≠ Gen 1, `egg_group` excluído, densidade do grafo completo, escopo de 175 Pokémon.

**Apresentação (10 min):**

- [ ] ~2 min — contexto + ontologia
- [ ] ~2 min — pipeline + trecho do `fetch.py`
- [ ] ~5 min — demo rodando consultas
- [ ] ~1 min — limitações e conclusão
- [ ] **Ensaio cronometrado** pelo menos 2× antes do dia 03/12.

---

## 5. Cronograma sugerido

| Semana | Foco | Entrega |
|---|---|---|
| 1 | Fase 1 + início da Fase 2 | `cache/` populado, `log_fetch.txt` |
| 2 | Fase 2 + Fase 3 | `kg.json` validado + `kg.py` com testes |
| 3 | Fase 4 + Fase 5 | demo funcional + figuras |
| 4 | Fase 6 | relatório + ensaio da apresentação |

---

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Internet cair na demo | Cache local + `kg.json` versionado no repositório |
| Rate limit da PokéAPI | Cache em disco + `sleep(0.1)` + 2ª execução com zero requests |
| Grafo completo ilegível | Projeções obrigatórias (Fase 5) |
| Cadeias evolutivas truncadas | Satélites cross-gen incluídos desde a Fase 1 |
| `kg.json` "feito à mão" (suspeita da banca) | `log_fetch.txt` + `cache/` brutos + script rerodável em 30s |
| Estouro das 3 páginas | Estrutura fixa de seções, escrita enxuta com tabelas |

---

## 7. Critérios de avaliação — checklist de autoavaliação

- [ ] Grafo com **≥ 50 nós** (temos ~270).
- [ ] **Entidades, relacionamentos e propriedades** presentes (sim: nós tipados, arestas rotuladas com props, nós com props).
- [ ] Código implementa **adicionar, remover, consultar** nós e arestas.
- [ ] Relatório cobre aplicação, base, potenciais e limitações.
- [ ] Apresentação mostra **grafo + aplicação rodando** em ≤ 10 min.


