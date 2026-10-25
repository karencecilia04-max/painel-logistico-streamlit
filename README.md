# Painel logístico

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white) ![Licença MIT](https://img.shields.io/badge/licença-MIT-informational?style=flat-square)

Plataforma de indicadores logísticos para acompanhamento das operações de importação.

![Dashboard de agentes](docs/indicadores.png)

<table>
<tr>
<td width="50%"><img src="docs/navios.png" alt="Atracação de navios"><br><sub>Atracação de navios por porto</sub></td>
<td width="50%"><img src="docs/frete.png" alt="Consulta de frete"><br><sub>Consulta de frete por agente e origem</sub></td>
</tr>
</table>

## Problema

A diretoria precisava acompanhar semanalmente o cenário logístico: oscilação dos valores de frete, parceiros com maior volume de embarques e cargas com embarque pendente. Os dados estavam distribuídos nas planilhas de follow-up das equipes, sem um meio adequado de consolidação e visualização.

## Lógica

- **Fonte única, sem retrabalho.** As equipes continuam preenchendo o follow-up como antes. O painel apenas lê essas planilhas, sem criar uma segunda base de dados.
- **Tratamento antes da análise.** Grafias diferentes de um mesmo local são unificadas, datas digitadas com erro são corrigidas quando a intenção é clara e registros inválidos são separados para conferência.
- **Indicadores orientados à decisão:** volume por agente de carga e por porto, chegada de navios, cargas aguardando embarque, frete médio por origem e agente, e comparativo entre períodos.
- **Simulação de custos.** Uma calculadora estima armazenagem, serviços do parceiro e frete rodoviário a partir de uma tabela de tarifas mantida pela própria equipe.
- **Relatório para apresentação.** Cada tela gera um PDF com os filtros aplicados.

> Todos os dados exibidos são fictícios.

## Tecnologias

Python, Streamlit, pandas, Plotly, matplotlib e Google Sheets API.
