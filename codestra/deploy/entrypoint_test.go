package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
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

func writeTestCertificate(t *testing.T, dnsName string, notBefore, notAfter time.Time) string {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: dnsName},
		DNSNames:     []string{dnsName},
		NotBefore:    notBefore,
		NotAfter:     notAfter,
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "server.crt")
	contents := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	if err := os.WriteFile(path, contents, 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestValidateServerCertificate(t *testing.T) {
	now := time.Now()
	valid := writeTestCertificate(t, otlpBindHost, now.Add(-time.Minute), now.Add(time.Hour))
	if err := validateServerCertificate(valid, otlpBindHost, now); err != nil {
		t.Fatalf("valid ingress certificate rejected: %v", err)
	}

	wrongName := writeTestCertificate(t, "otel-collector", now.Add(-time.Minute), now.Add(time.Hour))
	if err := validateServerCertificate(wrongName, otlpBindHost, now); err == nil {
		t.Fatal("certificate without the ingress DNS SAN was accepted")
	}
	expired := writeTestCertificate(t, otlpBindHost, now.Add(-2*time.Hour), now.Add(-time.Hour))
	if err := validateServerCertificate(expired, otlpBindHost, now); err == nil {
		t.Fatal("expired ingress certificate was accepted")
	}
}
