# Count release, federation, and privacy

`fedpath` separates local document-frequency computation from aggregation:

```python
local_counts = local_document_frequency(private_documents)
aggregate = aggregate_document_frequencies(released_count_maps)
```

This API makes the data boundary explicit. It does **not** by itself provide
secure aggregation, differential privacy, encrypted transport, client
authentication, poisoning resistance, or protection against inference from
rare counts.

## Minimal threat model

The built-in aggregation helper assumes:

- every participant intentionally releases its full count map;
- the aggregator may inspect every released map;
- participants and the aggregator are honest with respect to count integrity;
- transport security is supplied externally.

For stronger claims, deploy a secure-aggregation protocol so the aggregator
learns only an aggregate, and consider clipping, thresholding, or differential
privacy before releasing rare counts. Document the chosen adversary model and
privacy budget outside this library.
