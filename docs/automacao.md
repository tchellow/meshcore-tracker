# Como a automação funciona

Os pedidos saem **um de cada vez**, com pausa de 5 segundos entre eles. Eles nunca se sobrepõem: o próximo só sai depois que o anterior terminar. Com vários contatos, cada um pode demorar mais que o intervalo escolhido.

## Tempo de resposta

O programa mede quanto cada contato leva para responder e mantém uma média móvel, com peso de 30% para a medição nova.

### Espera

A espera é quanto o programa aguarda a resposta:

```text
espera = 3 × tempo médio, entre 10 e 60 segundos
```

Sem medição, usa 30 segundos. Se o rádio sugerir mais tempo para a rota, vale a sugestão, até o limite de 60 segundos.

### Intervalo real

O intervalo escolhido é um **mínimo**, contado do início de um pedido até o início do próximo:

```text
intervalo real = maior valor entre o escolhido e 3 × tempo médio
```

Assim, um contato ocupa o rádio em no máximo cerca de um terço do tempo. Por exemplo, com 15 segundos escolhidos:

| Resposta média | Espera | Intervalo real |
|---|---|---|
| 2 s | 10 s | 15 s |
| 8 s | 24 s | 24 s |
| 15 s | 45 s | 45 s |

## Falhas

Quando um contato não responde:

1. A média dele é descartada, e o próximo pedido volta à espera inicial. Isso permite medir um contato que ficou lento de repente.
2. O intervalo dobra a cada falha, até 4 horas. Se o intervalo escolhido for maior que isso, vale o escolhido.
3. Depois de **2 falhas seguidas**, se houver rota salva, ela é apagada e o pedido seguinte sai por flood. Uma falha só pode ser um pacote perdido, e o flood ocupa mais a malha.

Uma resposta sem GPS conta como resposta: não é falha nem apaga a rota. Se o cabo sair durante um pedido, isso também não conta contra o contato.

## Rotas

O firmware do rádio escolhe o caminho:

- **Sem rota conhecida:** o pedido sai por flood, e todo repetidor que o ouvir o retransmite.
- **Com rota conhecida:** o pedido segue pelos repetidores daquela rota.

Quando o rádio aprende uma rota nova, a coluna **Rota** é atualizada sozinha. A rota pode mudar entre pedidos, inclusive ficando mais curta.

## Recomendações

- Intervalos de 15 e 30 segundos ocupam bastante a malha, principalmente com vários hops. Use-os por pouco tempo.
- Veja a coluna **Última resposta** para conhecer o tempo real da sua malha.
