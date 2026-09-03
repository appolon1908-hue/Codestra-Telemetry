package main

import (
	"strings"
	"testing"
)

func TestValidateIdentity(t *testing.T) {
	source := strings.Repeat("a", 40)
	digest := "sha256:" + strings.Repeat("b", 64)
	image := "ghcr.io/appolon1908-hue/codestra-telemetry-opentelemetry@" + digest
	if err := validateIdentity(source, source, digest, image, source); err != nil {
		t.Fatalf("valid identity rejected: %v", err)
	}
	for name, values := range map[string][]string{
		"source mismatch":   {source, strings.Repeat("c", 40), digest, image, source},
		"embedded mismatch": {source, source, digest, image, strings.Repeat("c", 40)},
		"digest mismatch":   {source, source, "sha256:" + strings.Repeat("c", 64), image, source},
		"wrong repository":  {source, source, digest, "ghcr.io/example/collector@" + digest, source},
	} {
		t.Run(name, func(t *testing.T) {
			if err := validateIdentity(values[0], values[1], values[2], values[3], values[4]); err == nil {
				t.Fatal("invalid identity accepted")
			}
		})
	}
}

func TestValidateTopology(t *testing.T) {
	if err := validateTopology("platform", otlpBindHost, metricsBindHost); err != nil {
		t.Fatalf("valid topology rejected: %v", err)
	}
	for name, values := range map[string][]string{
		"unknown business": {"platfrom", otlpBindHost, metricsBindHost},
		"shared alias":     {"platform", "otel-collector", metricsBindHost},
		"swapped aliases":  {"platform", metricsBindHost, otlpBindHost},
	} {
		t.Run(name, func(t *testing.T) {
			if err := validateTopology(values[0], values[1], values[2]); err == nil {
				t.Fatal("invalid topology accepted")
			}
		})
	}
}
