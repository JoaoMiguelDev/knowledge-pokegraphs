# Knowledge PokéGraphs

Knowledge Graph do universo Pokémon construído sobre a [PokéAPI v2](https://pokeapi.co/api/v2),
desenvolvido como projeto da disciplina de **Algoritmos e Estrutura de Dados**.

## Sobre

O projeto modela Pokémon da Geração 1 (mais satélites cross-gen necessários para fechar
cadeias evolutivas) como um grafo de conhecimento com três tipos de nó — `Pokemon`, `Type`
e `Ability` — e relações como `has_type`, `has_ability`, `evolves_to` e o type chart
(`double_damage_to`, `half_damage_to`, `no_damage_to`, com multiplicador como propriedade
da aresta).

O núcleo do projeto — a classe `KnowledgeGraph`, as operações de manipulação e consulta e
a busca em largura — é implementado do zero com a biblioteca padrão do Python.
Dependências externas são usadas apenas na coleta (`requests`) e na visualização
(`networkx`, `matplotlib`).

## Requisitos

- Python >= 3.10
- Dependências externas: ver `requirements.txt`

## Como reproduzir

```bash
# 1. Clonar e entrar no repositório
git clone <url> knowledge-pokegraphs
cd knowledge-pokegraphs

# 2. Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Coletar dados da PokéAPI (popula data/cache/)
python fetch.py

# 5. Construir o grafo curado (gera data/kg.json)
python build_kg.py

# 6. Rodar a demonstração
python main.py

# 7. (Opcional) Gerar as figuras
python visualizar.py