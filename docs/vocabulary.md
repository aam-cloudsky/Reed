

Com o que essa arquitetura se parece?
1. Elm Architecture
2. Redux
3. CQRS
4. Actor Model
5. Apache NiFi: processor (node), flowfile (parcel)
6. Node-RED
7. ROS2
8. Unreal Engine Blueprint
9. LabVIEW
10. Simulink
11. Apache Airflow
12. Prefect
13. Luigi (Spotify)
14. Dagster: assets (parcel)
15. BehaviorTree.CPP
16. Unity Visual Scripting (Bolt)
17. Godot Visual Script
18. Akka Actor Model. (node)
19. Orleans
20. KNIME
21. Alteryx
22. RapidMiner
23. Apache Beam
24. Apache Flink
25. Kafka Streams
26. n8n: Webhook
27. Make (Integromat)
28. Zapier
29. Kepler Workflow
30. Taverna Workflow
31. QGIS Processing Modeler
32. ArcGIS ModelBuilder
33. Hamilton (DAGWorks) 
34. LangGraph
35. FastStream
36. Temporal.io
37. Ray
38. Celery
39. Dramatiq
40. Nameko
41. Salsa



* Hamilton → grafo inferido por funções e tipos;
* ROS2 → componentes independentes que cooperam;
* Redux/CQRS → Intent como entrada explícita do sistema;
* SkyWeaver → estado persistente compartilhado (Depot), sincronização (Outpost) e propagação baseada em snapshots/versionamento.



Quais padrões aparecem?
* Reactive Dataflow: o núcleo do sistema é um grafo onde transformações são disparadas por mudanças de estado.
* Pipes and Filters: cada Node transforma um conjunto de Consumed em Produced.
* Mediator: o Logistics coordena a sincronização entre Outposts e Depot, evitando acoplamento direto entre nós.
* Bridge (GoF): os BridgeNodes conectam dois domínios logísticos independentes.
* Command: as Intents representam comandos emitidos pela camada de aplicação.
* Event-driven Architecture: mudanças de estado propagam novos cálculos naturalmente.
* Ports and Adapters (Hexagonal): a camada de aplicação pode ser vista como um adaptador do domínio operacional, embora o seu modelo seja mais reativo do que uma arquitetura hexagonal tradicional.






3. Evoluir o Dispatcher para uma abstração

Não acople a arquitetura à ideia de fila. Pense em um Dispatcher com múltiplas implementações:

* Inline (síncrono)
* Thread
* AsyncIO
* RabbitMQ
* Redis Streams
* Kafka




## 1. Comparação entre plataformas
| Sistema | Paradigma | Unidade de processamento | Unidade de dado | Estado compartilhado | Tipagem | Reatividade | Distribuído | Observações |
|----------|-----------|--------------------------|-----------------|----------------------|---------|-------------|-------------|-------------|
| ROS2 | Publish/Subscribe | Node | Message | ❌ | Parcial | Eventos | ✅ | Comunicação por tópicos |
| Apache NiFi | Dataflow | Processor | FlowFile | ❌ | Fraca | Fluxo | ✅ | ETL e integração de dados |
| Node-RED | Dataflow | Node | Message | ❌ | Fraca | Eventos | Parcial | Automação visual |
| Dagster | Asset Graph | Asset / Op | Asset | Parcial | Forte | DAG | ✅ | Data Engineering |
| Hamilton | Function Graph | Function | Return Value | ❌ | Forte | DAG | ❌ | Inferência por tipos |
| Apache Airflow | Workflow DAG | Task | Artifact | ❌ | Parcial | Agendamento | ✅ | Orquestra pipelines |
| Temporal.io | Workflow Engine | Workflow / Activity | Event | Workflow State | Forte | Eventos | ✅ | Orquestração distribuída |
| Apache Beam | Dataflow | Transform | PCollection | ❌ | Forte | Stream / Batch | ✅ | Modelo unificado |
| SkyWeaver | Reactive Graph | Node | Parcel | ✅ Depot | Forte | Snapshot | Futuro | Provenance, Versionamento e Estado Compartilhado |





## 2. Glossário de nomenclatura
| SkyWeaver | Literatura | Exemplos |
|------------|------------|----------|
| Parcel | Asset / Data Object / FlowFile | Dagster, NiFi |
| Depot | State Store / Repository / Store | Redux, Kafka Streams |
| Outpost | Workspace / Context / Session / Transaction | Bancos de dados, Runtime Context |
| Flow | DAG / Pipeline / Workflow | Airflow, Hamilton |
| Node | Processor / Operator / Asset / Function | NiFi, Dagster |
| Logistics | Runtime / Execution Engine | Beam, Flink |
| BridgeNode | Adapter / Connector | GoF Bridge, Integration Layer |
| Provenance | Data Lineage | NiFi, Data Catalogs |
| Validity | Cache Invalidation / Dirty Flag | Build Systems |
| Command (futuro) | Command | CQRS |


## 3. Inspiração × Limitação × Contribuição
| Sistema | Inspiração aproveitada | Limitação identificada | Contribuição do SkyWeaver |
|----------|------------------------|------------------------|---------------------------|
| ROS2 | Componentização e comunicação entre nós | Baseado apenas em mensagens | Estado compartilhado persistente (Depot) + recomputação por snapshots |
| Dagster | Grafo tipado baseado em funções | Voltado para pipelines de dados | Grafo reativo para aplicações operacionais |
| Hamilton | Inferência automática de dependências | Não possui estado persistente | Depot + Outpost + Versionamento |
| Apache NiFi | Fluxo declarativo de processamento | Fluxo de documentos | Fluxo de estado tipado |
| Temporal | Execução distribuída e confiável | Orquestra workflows | Dispatcher desacoplado do modelo computacional |
| Redux | Estado centralizado | Lógica concentrada em reducers | Transformações distribuídas em um grafo reativo |
| CQRS | Separação entre comandos e processamento | Não define um modelo computacional | Commands integrados a Flows reativos |
| Apache Beam | Modelo unificado de processamento | Voltado para streaming e batch | Processamento incremental orientado a estado |




## 4. Comparação conceitual dos modelos
| Plataforma | Como modela o sistema |
|------------|-----------------------|
| Redux | Estado + Reducers |
| CQRS | Commands + Handlers |
| ROS2 | Nodes + Topics + Messages |
| Dagster | Assets + Dependencies |
| Hamilton | Functions + Types |
| NiFi | Processors + FlowFiles |
| Airflow | Tasks + DAG |
| Temporal | Workflows + Activities |
| SkyWeaver | Nodes + Parcels + Depot + Outposts + Flows |



## 5. Modelo computacional
| Característica | SkyWeaver |
|----------------|-----------|
| Grafo tipado | ✅ |
| Estado compartilhado | ✅ |
| Versionamento | ✅ |
| Proveniência | ✅ |
| Recomputação incremental | ✅ |
| Dependências declarativas | ✅ |
| Camadas (Application / Operational) | ✅ |
| Bridges entre camadas | ✅ |
| Commands | Planejado |
| Dispatcher síncrono | Planejado |
| Dispatcher assíncrono | Planejado |
| Distribuição transparente | Planejado |





## 6. Roadmap arquitetural
| Camada | Responsabilidade |
|---------|------------------|
| Frontend | Interface do usuário |
| Dispatcher | Recebe Commands e dispara Application Flows |
| Application Layer | Casos de uso, UI, integração |
| Downstream Bridge | Traduz Commands para o domínio operacional |
| Operational Layer | Processamento reativo e regras de negócio |
| Upstream Bridge | Retorna resultados para Application Layer |
| Application Layer | Constrói ViewModels, Artefatos e Estado da Interface |




## 6. Roadmap arquitetural
| Entidade | Padrão de design |
|---------|------------------|
depot |     Blackboard,     Shared State,     State Store

Outpost

Concordo.

Até agora eu não encontrei um termo melhor.

Ele é um misto de:

* Workspace
* Transaction
* Session
* Context


Propagação da invalidade:
Invalidation Propagation -> dirty flag
A ideia de Dirty Flag é clássica em Game Engines.
Transform

    ↓

Dirty

    ↓

Recompute



## Dagster

### Paradigma
Asset Graph

### Unidade Computacional
Asset / Op

### Unidade de Dados
Asset

### Como executa
DAG

### Como modela dependências
Inferência declarativa

### Estado Compartilhado
Parcial

### Distribuição
Sim

### O que inspira o SkyWeaver
...

### Limitações
...

### O que o SkyWeaver propõe de diferente
...




ROS 2
    modularidade, mediação e lifecycle

Dagster
    dependências orientadas a artefatos

Salsa
    recomputação incremental e sob demanda

Flow-Based Programming
    aplicações como redes de componentes

Blackboard
    estado compartilhado e ativação por contexto




5. Blackboard systems: estado compartilhado e especialistas

A arquitetura blackboard trabalha com uma base compartilhada atualizada por módulos especializados. Cada especialista observa o estado, verifica se suas condições são satisfeitas e contribui com resultados parciais. Historicamente, ela foi usada para integrar módulos heterogêneos em problemas cuja solução emerge de múltiplas fontes de conhecimento.


Blackboard                  SkyWeaver

Shared knowledge base       Depot
Knowledge source            Unit
Blackboard entries          Parcels
Control component           Core/runtime
Activation condition        dependency + validity





Uma base documental que realmente vale construir

Eu não começaria escrevendo dezenas de páginas sobre todo o framework. Montaria cinco documentos pequenos, fundamentados nessas famílias:

1. Computational Model
    O que é Unit, Parcel, produtor, dependência, validade e propagação.
2. Runtime Model
    Registro, bootstrap, bind, unbind, close, erro e concorrência.
3. Application Composition Model
    Como Services, Flows e Bridges selecionam e expõem capacidades.
4. Dependency and Materialization Model
    Grafo autoritativo de Parcels, grafo derivado de Units, invalidação e recomputação.
5. Architectural Comparison
    ROS 2, Dagster, Salsa, FBP/NiFi e Blackboard: o que foi adotado, adaptado e rejeitado.





# Nova divisão


Skyweaver x Gerador de fluxos (preciso de um nome)


┌─────────────────────────────────────────┐
│              SkyWeaver                  │
│-----------------------------------------│
│ Services                               │
│ Tools                                  │
│ Frontend                               │
│ Gateway                                │
│ Bridges                                │
│ Application Layer                      │
│ Assets                                 │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│             Loom.                       │
│-----------------------------------------│
│ Flow Engine                            │
│ Incremental processing                    │
│ Dependency Graph                       │
│ Shared State                           │
│ Messaging                              │
└─────────────────────────────────────────┘



O gerador de fluxos é um programa à parte. Ele tem 4 camadas (até então):

1. Transporte
2. Sincronia

3. Computação incremental e sob demanda

4. Lógica: grafo de fluxo de dados
(talvez haja um nome melhor para a camada lógica)
(talvez a camada 3 e 4 sejam uma única)

## 1. Camada de Transporte: ROS 2

ROS 2                     SkyWeaver

Node                      Unit (Node)
Message                   Parcel
Topic / middleware        Bus (Port + MessageHub)
Lifecycle Node            Unit com bind/unbind/close (?)
Composition container     Application bootstrap (?)


ROS 2: componentes, comunicação e lifecycle

O ROS 2 é provavelmente a referência mais próxima para entender seus Units. Cada node deve ter uma finalidade modular e se comunica com outros nodes por mecanismos mediados pelo runtime, em vez de conhecer diretamente suas implementações. O ROS 2 também separa o conceito de node da forma de composição e oferece nodes com lifecycle controlado. 






## 2. Camada de Sincronia é equivalente ao blackboard:
Blackboard                  SkyWeaver

Shared knowledge base       Depot (Centrilized Repository)
Knowledge source            Unit (Node)
Blackboard entries          Parcels
Control component           Core (? acho que n tenho componente de controle)
Activation condition        dependency + validity


Portanto, poderíamos até adotar nomeclaturas melhores.


Dagster: dependências centradas nos artefatos

Essa talvez seja a referência mais reveladora para o seu Outpost.

O Dagster possui o conceito de software-defined asset: uma definição combina a identidade de um artefato com a função capaz de produzi-lo. O grafo é fortemente orientado pelos dados materializados, não apenas pelas tarefas executadas.


## 3. Camada de Computação incremental e sob demanda

O Salsa é possivelmente a referência mais importante para a sua arquitetura reativa.

Ele é um framework para computações incrementais e sob demanda: entradas mudam, o sistema rastreia dependências entre consultas, reutiliza resultados válidos e recalcula somente o que for necessário. Sua origem está ligada às técnicas de recompilação incremental usadas pelo compilador Rust.

Salsa                       SkyWeaver

Input                       Parcel de entrada
Tracked computation         método produtor (process do node ?)
Query dependency            depends_on (parcel dependency)
Memoized result             Parcel materializado
Revision/change             atualização + validity (invalidation policy)
On-demand recomputation     propagação reativa (trig on invalidation)
Database                    Depot

## 4. Camada Lógica: Flow-Based Programming 

Flow-Based Programming define aplicações como redes de processos independentes, conectados externamente e trocando pacotes de informação por portas nomeadas. A configuração das conexões é separada da implementação dos processos. 


Process       → Unit (Node)
Packet        → Parcel
Port          → Port
Network       → Flow