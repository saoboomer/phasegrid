# PhaseGrid secure transport prototype

This branch adds an experimental authenticated envelope without changing the
existing optical encoder or decoder. Its size makes it unsuitable for long
messages at current symbol timing.

## Security design

- Argon2id derives a 256-bit key from a high-entropy passphrase and per-message
  128-bit salt (64 MiB, three passes, four lanes).
- AES-256-GCM encrypts and authenticates the message and its version/salt/nonce
  header. The nonce is 96 bits and freshly generated per message.
- Reed-Solomon RS(255,239) adds 16 parity bytes after encryption. It can correct
  up to 8 unknown byte errors, or errors/erasures satisfying 2e+v <= 16.
- Each byte is represented by two A-Z symbols. A valid pair maps to one byte;
  impossible pairs are passed to the Reed-Solomon decoder as erasures.
- A persistent SQLite ledger rejects a previously accepted salt+nonce pair.
  The replay claim is committed only after AEAD authentication succeeds and
  before plaintext is returned.

The receiver must never release plaintext before all FEC and AEAD checks pass.
Authentication errors do not distinguish a wrong passphrase from tampering.

## Important constraints

1. The secure envelope is one RS block, so plaintext is limited to 191 UTF-8
   bytes. Longer messages require authenticated chunking with a unique nonce
   and replay identity per chunk, plus ordering and truncation protection.
2. Two optical letters represent each code byte. The maximum 255-byte RS
   codeword therefore becomes 510 optical symbols. At the current 4.0-second
   character interval plus 0.5-second delimiter, a maximum-size message takes
   about 38 minutes. Even a short message has substantial fixed cryptographic
   overhead. This is an experiment, not yet a practical secure messenger.
3. The replay database must be durable and shared across every receiver
   instance. Local ephemeral server storage is not sufficient. If the ledger
   cannot be persisted, secure decoding must fail closed.
4. RS correction repairs bounded substitutions/erasures. It does not solve
   insertions, deletions, frame loss, or synchronization errors.
5. AES-GCM provides confidentiality and integrity, not sender identity when
   multiple people share the same passphrase, non-repudiation, traffic-analysis
   resistance, or protection against a compromised endpoint.
6. This code has not been independently audited. Treat it as a prototype.

## Soft-decision decoding

The phasegrid_softdecode module adds Gaussian maximum-likelihood soft decoding
for the existing 26-dimensional codebook. For observation y and codeword c_i:

    P(i|y) proportional to exp(-||y-c_i||^2/(2 sigma^2)) P(i)

It estimates scalar noise sigma from known pilot captures after a global
gain/offset fit. The current protocol does not yet transmit dedicated pilots,
and real camera noise may not be isotropic Gaussian. Returned posteriors are
not calibrated correctness probabilities until validated on held-out captures.

## Install and test

    pip install argon2-cffi cryptography reedsolo numpy pytest
    pytest -q

## Next engineering step

A useful throughput improvement needs a new modulation profile, not merely a
faster Python loop. The present 26-ary symbol channel carries at most
log2(26) = 4.70 bits per character interval. Explore multi-dimensional coded
modulation only after measuring feature noise, clipping, and camera aliasing.
Compare bit-error rate at equal optical energy and false-accept probability;
do not infer capacity from the number of basis vectors alone.
