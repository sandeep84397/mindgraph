# Transformer Architecture

## Summary

Transformer architecture use self-attention mechanism for sequence-to-sequence tasks. Introduced in "Attention Is All You Need" paper by Vaswani et al. 2017.

## Details

### Self-Attention

Self-attention compute weighted sum of all positions in sequence. Each position attend to every other position. Complexity O(n^2) with sequence length.

```python
def self_attention(Q, K, V):
    scores = Q @ K.T / sqrt(d_k)
    weights = softmax(scores)
    return weights @ V
```

### Multi-Head Attention

Multiple attention heads run in parallel. Each head learn different representation subspace. Outputs concatenated and projected.

### Feed-Forward Network

Two linear transformations with ReLU activation between them:

```python
FFN(x) = max(0, xW1 + b1)W2 + b2
```

## References

- raw/attention_is_all_you_need.pdf
- https://arxiv.org/abs/1706.03762

## See Also

- [[Self Attention]]
- [[BERT]]
- [[GPT]]
