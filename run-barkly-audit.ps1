param(
  [Parameter(Mandatory=$true)]
  [string]$Output
)

python -m tools.barkly_audit $Output
exit $LASTEXITCODE
