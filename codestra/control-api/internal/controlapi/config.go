package controlapi

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"slices"
	"strings"
)

const RegistrySchemaVersion = "1.0.0"

var (
	serviceIDPattern  = regexp.MustCompile(`^[a-z][a-z0-9-]{1,62}$`)
	envNamePattern    = regexp.MustCompile(`^CODESTRA_[A-Z0-9_]+$`)
	repositoryPattern = regexp.MustCompile(`^appolon1908-hue/[A-Za-z0-9._-]+$`)
)

type Registry struct {
	SchemaVersion        string            `json:"schemaVersion"`
	ExpectedServiceCount int               `json:"expectedServiceCount"`
	ContractSchema       ContractSchemaRef `json:"contractSchema"`
	Services             []Service         `json:"services"`
	Edges                []Edge            `json:"edges"`
}

type ContractSchemaRef struct {
	Repository     string `json:"repository"`
	Path           string `json:"path"`
	SourceRevision string `json:"sourceRevision"`
	Version        string `json:"version"`
}

type Service struct {
	ID                string      `json:"id"`
	DisplayName       string      `json:"displayName"`
	Component         string      `json:"component"`
	Repository        string      `json:"repository"`
	CanonicalHostname string      `json:"canonicalHostname"`
	AuthorityRole     string      `json:"authorityRole"`
	DeploymentClass   string      `json:"deploymentClass"`
	NativeExposure    string      `json:"nativeExposure"`
	BaseURLEnv        string      `json:"baseUrlEnvironment"`
	TimeoutMS         int         `json:"timeoutMs"`
	Health            ProbeConfig `json:"health"`
	Readiness         ProbeConfig `json:"readiness"`
	Auth              AuthConfig  `json:"auth"`
	Release           ReleaseRef  `json:"release"`
	Contract          ContractRef `json:"contract"`
	Signals           []string    `json:"signals"`
	DependsOn         []string    `json:"dependsOn"`
}

type ProbeConfig struct {
	Path             string `json:"path"`
	AcceptedStatuses []int  `json:"acceptedStatuses"`
}

type AuthConfig struct {
	BearerTokenFileEnv string `json:"bearerTokenFileEnvironment,omitempty"`
	CAFileEnv          string `json:"caFileEnvironment,omitempty"`
	ClientCertFileEnv  string `json:"clientCertFileEnvironment,omitempty"`
	ClientKeyFileEnv   string `json:"clientKeyFileEnvironment,omitempty"`
}

type ReleaseRef struct {
	SourceRevisionEnv string `json:"sourceRevisionEnvironment"`
	ImageDigestEnv    string `json:"imageDigestEnvironment"`
}

type ContractRef struct {
	Path    string `json:"path"`
	Version string `json:"version"`
}

type Edge struct {
	From     string `json:"from"`
	To       string `json:"to"`
	Signal   string `json:"signal"`
	Protocol string `json:"protocol"`
	Purpose  string `json:"purpose"`
	Mutating bool   `json:"mutating"`
}

func LoadRegistry(path string) (Registry, error) {
	file, err := os.Open(path)
	if err != nil {
		return Registry{}, fmt.Errorf("open registry: %w", err)
	}
	defer file.Close()
	return DecodeRegistry(file)
}

func DecodeRegistry(reader io.Reader) (Registry, error) {
	decoder := json.NewDecoder(io.LimitReader(reader, 2<<20))
	decoder.DisallowUnknownFields()
	var registry Registry
	if err := decoder.Decode(&registry); err != nil {
		return Registry{}, fmt.Errorf("decode registry: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return Registry{}, errors.New("decode registry: trailing JSON value")
	}
	if err := registry.Validate(); err != nil {
		return Registry{}, err
	}
	return registry, nil
}

func (registry Registry) Validate() error {
	if registry.SchemaVersion != RegistrySchemaVersion {
		return fmt.Errorf("unsupported registry schemaVersion %q", registry.SchemaVersion)
	}
	if registry.ExpectedServiceCount < 1 || registry.ExpectedServiceCount != len(registry.Services) {
		return fmt.Errorf("expectedServiceCount=%d does not match services=%d", registry.ExpectedServiceCount, len(registry.Services))
	}
	if err := validateSchemaRef(registry.ContractSchema); err != nil {
		return err
	}
	ids := make(map[string]struct{}, len(registry.Services))
	repositories := make(map[string]struct{}, len(registry.Services))
	for index, service := range registry.Services {
		if err := service.Validate(); err != nil {
			return fmt.Errorf("services[%d]: %w", index, err)
		}
		if _, exists := ids[service.ID]; exists {
			return fmt.Errorf("duplicate service id %q", service.ID)
		}
		if _, exists := repositories[service.Repository]; exists {
			return fmt.Errorf("duplicate service repository %q", service.Repository)
		}
		ids[service.ID] = struct{}{}
		repositories[service.Repository] = struct{}{}
	}
	for index, edge := range registry.Edges {
		if _, ok := ids[edge.From]; !ok {
			return fmt.Errorf("edges[%d]: unknown from service %q", index, edge.From)
		}
		if _, ok := ids[edge.To]; !ok {
			return fmt.Errorf("edges[%d]: unknown to service %q", index, edge.To)
		}
		if edge.From == edge.To {
			return fmt.Errorf("edges[%d]: self edges are not allowed", index)
		}
		if strings.TrimSpace(edge.Signal) == "" || strings.TrimSpace(edge.Protocol) == "" || strings.TrimSpace(edge.Purpose) == "" {
			return fmt.Errorf("edges[%d]: signal, protocol, and purpose are required", index)
		}
		if edge.Mutating {
			return fmt.Errorf("edges[%d]: mutating suite integrations are prohibited", index)
		}
	}
	return nil
}

func validateSchemaRef(ref ContractSchemaRef) error {
	if ref.Repository != "appolon1908-hue/Codestra-Telemetry" {
		return errors.New("contractSchema.repository must be appolon1908-hue/Codestra-Telemetry")
	}
	if ref.Path != "codestra/api/service-contract.schema.json" {
		return errors.New("contractSchema.path must be codestra/api/service-contract.schema.json")
	}
	if !regexp.MustCompile(`^[0-9a-f]{40}$`).MatchString(ref.SourceRevision) {
		return errors.New("contractSchema.sourceRevision must be an immutable 40-character Git SHA")
	}
	if ref.Version != "1.0.0" {
		return errors.New("contractSchema.version must be 1.0.0")
	}
	return nil
}

func (service Service) Validate() error {
	if !serviceIDPattern.MatchString(service.ID) {
		return fmt.Errorf("invalid id %q", service.ID)
	}
	if service.Component != service.ID {
		return errors.New("component must equal id")
	}
	if strings.TrimSpace(service.DisplayName) == "" || strings.TrimSpace(service.AuthorityRole) == "" {
		return errors.New("displayName and authorityRole are required")
	}
	if !repositoryPattern.MatchString(service.Repository) {
		return fmt.Errorf("invalid repository %q", service.Repository)
	}
	if strings.TrimSpace(service.CanonicalHostname) == "" || strings.ContainsAny(service.CanonicalHostname, "/:@") {
		return errors.New("canonicalHostname must be a hostname without scheme or port")
	}
	if !slices.Contains([]string{"central", "agent"}, service.DeploymentClass) {
		return fmt.Errorf("invalid deploymentClass %q", service.DeploymentClass)
	}
	if !slices.Contains([]string{"internal_private", "loopback_edge_only", "private_strong_auth"}, service.NativeExposure) {
		return fmt.Errorf("invalid nativeExposure %q", service.NativeExposure)
	}
	if !envNamePattern.MatchString(service.BaseURLEnv) {
		return fmt.Errorf("invalid baseUrlEnvironment %q", service.BaseURLEnv)
	}
	if service.TimeoutMS < 250 || service.TimeoutMS > 10000 {
		return errors.New("timeoutMs must be between 250 and 10000")
	}
	if err := service.Health.Validate("health"); err != nil {
		return err
	}
	if err := service.Readiness.Validate("readiness"); err != nil {
		return err
	}
	for _, name := range []string{
		service.Auth.BearerTokenFileEnv,
		service.Auth.CAFileEnv,
		service.Auth.ClientCertFileEnv,
		service.Auth.ClientKeyFileEnv,
		service.Release.SourceRevisionEnv,
		service.Release.ImageDigestEnv,
	} {
		if name != "" && !envNamePattern.MatchString(name) {
			return fmt.Errorf("invalid environment variable name %q", name)
		}
	}
	if (service.Auth.ClientCertFileEnv == "") != (service.Auth.ClientKeyFileEnv == "") {
		return errors.New("client certificate and key environment variables must be configured together")
	}
	if service.Release.SourceRevisionEnv == "" || service.Release.ImageDigestEnv == "" {
		return errors.New("release source revision and image digest environments are required")
	}
	if service.Contract.Path != "codestra/api/service-contract.v1.json" || service.Contract.Version != "1.0.0" {
		return errors.New("contract path/version must reference the local V1 service contract")
	}
	if len(service.Signals) == 0 {
		return errors.New("at least one signal is required")
	}
	return nil
}

func (probe ProbeConfig) Validate(name string) error {
	if !strings.HasPrefix(probe.Path, "/") || strings.HasPrefix(probe.Path, "//") || strings.ContainsAny(probe.Path, "\r\n") {
		return fmt.Errorf("%s.path must be a safe absolute path", name)
	}
	if len(probe.AcceptedStatuses) == 0 {
		return fmt.Errorf("%s.acceptedStatuses cannot be empty", name)
	}
	seen := map[int]struct{}{}
	for _, status := range probe.AcceptedStatuses {
		if status < 100 || status > 599 {
			return fmt.Errorf("%s has invalid accepted status %d", name, status)
		}
		if _, ok := seen[status]; ok {
			return fmt.Errorf("%s has duplicate accepted status %d", name, status)
		}
		seen[status] = struct{}{}
	}
	return nil
}
