package controlapi

import (
	"strings"
	"testing"
)

const testSchemaRevision = "0123456789abcdef0123456789abcdef01234567"

func validRegistry() Registry {
	return Registry{
		SchemaVersion:        RegistrySchemaVersion,
		ExpectedServiceCount: 1,
		ContractSchema: ContractSchemaRef{
			Repository:     "appolon1908-hue/Codestra-Telemetry",
			Path:           "codestra/api/service-contract.schema.json",
			SourceRevision: testSchemaRevision,
			Version:        "1.0.0",
		},
		Services: []Service{
			{
				ID:                "prometheus",
				DisplayName:       "Prometheus",
				Component:         "prometheus",
				Repository:        "appolon1908-hue/Codestra-Prometheus",
				CanonicalHostname: "prom.codestra.media",
				AuthorityRole:     "metrics-authority",
				DeploymentClass:   "central",
				NativeExposure:    "internal_private",
				BaseURLEnv:        "CODESTRA_PROMETHEUS_URL",
				TimeoutMS:         1000,
				Health:            ProbeConfig{Path: "/-/healthy", AcceptedStatuses: []int{200}},
				Readiness:         ProbeConfig{Path: "/-/ready", AcceptedStatuses: []int{200}},
				Release: ReleaseRef{
					SourceRevisionEnv: "CODESTRA_PROMETHEUS_SOURCE_REVISION",
					ImageDigestEnv:    "CODESTRA_PROMETHEUS_IMAGE_DIGEST",
				},
				Contract:  ContractRef{Path: "codestra/api/service-contract.v1.json", Version: "1.0.0"},
				Signals:   []string{"metrics"},
				DependsOn: []string{},
			},
		},
	}
}

func TestRegistryValidation(t *testing.T) {
	registry := validRegistry()
	if err := registry.Validate(); err != nil {
		t.Fatalf("valid registry rejected: %v", err)
	}
	registry.Services[0].BaseURLEnv = "PROMETHEUS_URL"
	if err := registry.Validate(); err == nil {
		t.Fatal("unsafe environment variable name accepted")
	}
}

func TestDecodeRegistryRejectsUnknownFields(t *testing.T) {
	payload := `{
	  "schemaVersion":"1.0.0",
	  "expectedServiceCount":0,
	  "contractSchema":{},
	  "services":[],
	  "edges":[],
	  "unexpected":true
	}`
	if _, err := DecodeRegistry(strings.NewReader(payload)); err == nil {
		t.Fatal("unknown field accepted")
	}
}
