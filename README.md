# DDTank Calculator

Calculadora web independente para auxiliar nos disparos do DDTank Clássico.

## V1

- Cálculo de Full e Semi-Full.
- Métodos de ângulo fixo: 65°, 50°, 30° e 20°.
- Tabelas de força transcritas da imagem enviada pelo usuário.
- Direção do vento definida como **a favor** ou **contra** em relação à direção do disparo.
- Ajuste manual de altura de -3 a +3 pontos de força.
- Atalhos de teclado para operar sem depender tanto do mouse.
- Registro manual do ângulo e da força realmente usados, comparados à recomendação.
- Histórico local dos últimos tiros (apenas durante a sessão atual).

## Executar

Abra `index.html` diretamente no navegador. Não precisa instalar dependências, servidor ou API.

## Atalhos

| Atalho | Ação |
|---|---|
| `Alt + 1` a `Alt + 6` | Full, Semi-Full, 65°, 50°, 30°, 20° |
| `Alt + D` | Focar distância |
| `Alt + W` | Focar vento |
| `Alt + A` | Focar ângulo usado no jogo |
| `Alt + F` | Focar força usada no jogo |
| `Alt + S` | Focar força do Semi-Full |
| `Alt + ←` | Vento contra |
| `Alt + →` | Vento a favor |

## Regras implementadas na V1

- Full: ângulo = 90 - distância + (vento × 2, com sinal conforme a direção); força 95.
- Semi-Full: ângulo = 90 - (distância × 2) + (vento × 2, com sinal); força inicial 63, ajustável entre 60 e 65.
- 65° e 50°: ângulo base fixo + compensação de vento × 2.
- 30°: ângulo base fixo + compensação de vento × 1.
- 20°: vento ignorado.
- Para consultar as tabelas, a distância é arredondada ao inteiro mais próximo e limitada ao intervalo de 1 a 20.
- O ajuste de altura é manual e soma diretamente à força.

## Limitações conhecidas / próximos passos

- A compensação de força para vento quebrado ainda não foi automatizada: a descrição recebida informa uma aproximação de 1 ponto por 0,1 de sobra, mas precisamos validar a regra em jogo antes de codificá-la.
- Distâncias fracionárias são arredondadas para consulta das tabelas. Precisamos validar se esse arredondamento corresponde ao comportamento do servidor.
- A V1 não captura a tela do jogo nem detecta ângulo/força automaticamente. O fluxo inicial usa campos rápidos e atalhos.
- Reconhecimento de tela (OCR) e janela overlay serão avaliados numa etapa posterior, com o jogo rodando no Windows.

## Tabelas de força da imagem

Os índices correspondem às distâncias inteiras de 1 a 20.

- 20°: 10, 19, 25, 30, 36, 40, 44, 48, 51, 54, 57, 60, 63, 66, 69, 72, 74, 76, 78, 80
- 30°: 14, 20, 24, 28, 32, 35, 38, 41, 44, 47, 50, 52, 55, 57, 60, 62, 65, 67, 69, 72
- 50°: 14, 20, 24, 28, 32, 35, 39, 42, 44, 48, 50, 53, 55, 58, 60, 63, 65, 68, 70, 72
- 65°: 13, 20, 26, 31, 37, 41, 44, 48, 53, 56, 58, 61, 64, 67, 70, 73, 76, 79, 82, 85

## Observação

Os resultados são recomendações iniciais baseadas nas regras e na tabela fornecidas. Terreno, obstáculos, altura e particularidades do servidor podem exigir testes e ajustes manuais.

## Modo janela compacta (1366 × 768)

A página tem um botão **Janela compacta** no cabeçalho. Clique nele para abrir uma segunda janela de aproximadamente 390 × 740 pixels, com os resultados em destaque e menos elementos auxiliares.

Para usar lado a lado:
1. Coloque o DDTank em modo janela.
2. Abra a calculadora no navegador e clique em **Janela compacta**.
3. Posicione as duas janelas como preferir.
4. Se quiser manter a calculadora visível sobre o jogo, use Microsoft PowerToys > Always On Top (atalho padrão `Win + Ctrl + T`).

**Limitação:** os atalhos de teclado da página só funcionam enquanto a janela da calculadora estiver em foco. Eles não capturam teclas globais enquanto o DDTank está ativo. Para isso, será necessário um aplicativo auxiliar Windows na próxima etapa.
