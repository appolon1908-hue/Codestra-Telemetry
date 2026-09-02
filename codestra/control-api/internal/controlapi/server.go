package controlapi

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const APIVersion = "codestra.io/v1"

var correlationPattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,128}$`)

type ServerOptions struct {
	Registry        Registry
	Prober          Prober
	OpenAPI         []byte
	AuthMode        string
	BearerTokenFile string
	MaxConcurrency  int
}

type Server struct {
	registry        Registry
	prober          Prober
	openAPI         []byte
	authMode        string
	bearerTokenFile string
	maxConcurrency  int
	probeRequests   atomic.Uint64
	probeFailures   atomic.Uint64
}

type errorResponse struct {
	APIVersion    string `json:"apiVersion"`
	Kind          string `json:"kind"`
	Code          string `json:"code"`
	Message       string `json:"message"`
	CorrelationID string `json:"correlationId"`
}

func NewServer(options ServerOptions) (*Server, error) {
	if err := options.Registry.Validate(); err != nil {
		return nil, err
	}
	if options.Prober == nil {
		options.Prober = HTTPProber{}
	}
	if options.AuthMode == "" {
		options.AuthMode = "required"
	}
	if options.AuthMode != "required" && options.AuthMode != "disabled" {
		return nil, fmt.Errorf("unsupported auth mode %q", options.AuthMode)
	}
	if options.AuthMode == "required" && strings.TrimSpace(options.BearerTokenFile) == "" {
		return nil, fmt.Errorf("bearer token file is required when auth mode is required")
	}
	if options.MaxConcurrency == 0 {
		options.MaxConcurrency = 6
	}
	if options.MaxConcurrency < 1 || options.MaxConcurrency > 32 {
		return nil, fmt.Errorf("max concurrency must be between 1 and 32")
	}
	return &Server{
		registry:        options.Registry,
		prober:          options.Prober,
		openAPI:         append([]byte(nil), options.OpenAPI...),
		authMode:        options.AuthMode,
		bearerTokenFile: options.BearerTokenFile,
		maxConcurrency:  options.MaxConcurrency,
	}, nil
}

func (server *Server) Handler() http.Handler {
	return http.HandlerFunc(server.serveHTTP)
}

func (server *Server) serveHTTP(response http.ResponseWriter, request *http.Request) {
	correlationID := correlationID(request.Header.Get("X-Correlation-ID"))
	setCommonHeaders(response, correlationID)
	if request.Method == http.MethodOptions {
		response.Header().Set("Allow", "GET, HEAD, OPTIONS")
		response.WriteHeader(http.StatusNoContent)
		return
	}
	if request.Method != http.MethodGet && request.Method != http.MethodHead {
		response.Header().Set("Allow", "GET, HEAD, OPTIONS")
		server.writeError(response, request, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "This control plane is read-only.", correlationID)
		return
	}

	path := request.URL.Path
	if path == "/healthz" {
		server.writeJSON(response, request, http.StatusOK, map[string]any{
			"apiVersion":    APIVersion,
			"kind":          "ControlPlaneHealth",
			"state":         "up",
			"correlationId": correlationID,
		})
		return
	}
	if path == "/readyz" {
		if server.authMode == "required" {
			if _, err := readControlToken(server.bearerTokenFile); err != nil {
				server.writeError(response, request, http.StatusServiceUnavailable, "AUTH_NOT_READY", "Control-plane authentication is not ready.", correlationID)
				return
			}
		}
		server.writeJSON(response, request, http.StatusOK, map[string]any{
			"apiVersion":    APIVersion,
			"kind":          "ControlPlaneReadiness",
			"state":         "ready",
			"services":      len(server.registry.Services),
			"correlationId": correlationID,
		})
		return
	}
	if !server.authorized(request) {
		response.Header().Set("WWW-Authenticate", `Bearer realm="codestra-observability-control-api"`)
		server.writeError(response, request, http.StatusUnauthorized, "UNAUTHORIZED", "Authentication is required.", correlationID)
		return
	}

	switch {
	case path == "/metrics":
		server.writeMetrics(response, request)
	case path == "/openapi.json":
		server.writeOpenAPI(response, request)
	case path == "/api/v1/capabilities":
		server.writeCapabilities(response, request, correlationID)
	case path == "/api/v1/services":
		server.writeServices(response, request, correlationID)
	case strings.HasPrefix(path, "/api/v1/services/"):
		server.writeServiceRoute(response, request, correlationID)
	case path == "/api/v1/health":
		server.writeAggregateHealth(response, request, correlationID)
	case path == "/api/v1/topology":
		server.writeTopology(response, request, correlationID)
	case path == "/api/v1/contracts":
		server.writeContracts(response, request, correlationID)
	case path == "/api/v1/releases":
		server.writeReleases(response, request, correlationID)
	default:
		server.writeError(response, request, http.StatusNotFound, "NOT_FOUND", "The requested resource does not exist.", correlationID)
	}
}

func (server *Server) authorized(request *http.Request) bool {
	if server.authMode == "disabled" {
		return true
	}
	expected, err := readControlToken(server.bearerTokenFile)
	if err != nil {
		return false
	}
	provided := strings.TrimSpace(request.Header.Get("Authorization"))
	if !strings.HasPrefix(provided, "Bearer ") {
		return false
	}
	provided = strings.TrimSpace(strings.TrimPrefix(provided, "Bearer "))
	if len(expected) != len(provided) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(expected), []byte(provided)) == 1
}

func readControlToken(file string) (string, error) {
	content, err := os.ReadFile(file)
	if err != nil {
		return "", err
	}
	if len(content) == 0 || len(content) > 64*1024 {
		return "", fmt.Errorf("invalid control token file size")
	}
	token := strings.TrimSpace(string(content))
	if token == "" || strings.ContainsAny(token, "\r\n") {
		return "", fmt.Errorf("invalid control token")
	}
	return token, nil
}

func (server *Server) writeCapabilities(response http.ResponseWriter, request *http.Request, correlationID string) {
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "ControlPlaneCapabilities",
		"correlationId": correlationID,
		"capabilities": map[string]bool{
			"serviceDiscovery":       true,
			"aggregateHealth":        true,
			"readinessReadback":      true,
			"topologyReadback":       true,
			"contractDiscovery":      true,
			"releaseIdentityReadback": true,
			"nativeApiProxy":         false,
			"mutationProxy":          false,
			"secretValueReadback":    false,
		},
	})
}

func (server *Server) writeServices(response http.ResponseWriter, request *http.Request, correlationID string) {
	items := make([]map[string]any, 0, len(server.registry.Services))
	for _, service := range server.registry.Services {
		items = append(items, serviceSummary(service))
	}
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "ServiceList",
		"correlationId": correlationID,
		"count":         len(items),
		"items":         items,
	})
}

func serviceSummary(service Service) map[string]any {
	return map[string]any{
		"id":                service.ID,
		"displayName":       service.DisplayName,
		"component":         service.Component,
		"repository":        service.Repository,
		"canonicalHostname": service.CanonicalHostname,
		"authorityRole":     service.AuthorityRole,
		"deploymentClass":   service.DeploymentClass,
		"nativeExposure":    service.NativeExposure,
		"configured":        strings.TrimSpace(os.Getenv(service.BaseURLEnv)) != "",
		"signals":           service.Signals,
		"dependsOn":         service.DependsOn,
	}
}

func (server *Server) writeServiceRoute(response http.ResponseWriter, request *http.Request, correlationID string) {
	remaining := strings.TrimPrefix(request.URL.Path, "/api/v1/services/")
	parts := strings.Split(strings.Trim(remaining, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		server.writeError(response, request, http.StatusNotFound, "NOT_FOUND", "The requested service does not exist.", correlationID)
		return
	}
	service, ok := server.service(parts[0])
	if !ok {
		server.writeError(response, request, http.StatusNotFound, "SERVICE_NOT_FOUND", "The requested service does not exist.", correlationID)
		return
	}
	if len(parts) == 1 {
		server.writeJSON(response, request, http.StatusOK, map[string]any{
			"apiVersion":    APIVersion,
			"kind":          "Service",
			"correlationId": correlationID,
			"service":       serviceSummary(service),
			"contract":      service.Contract,
			"release":       releaseReadback(service),
		})
		return
	}
	if len(parts) == 2 && parts[1] == "health" {
		server.probeRequests.Add(1)
		result := server.prober.Probe(request.Context(), service, correlationID)
		if result.State != "ready" && result.State != "unconfigured" {
			server.probeFailures.Add(1)
		}
		status := http.StatusOK
		if result.State == "unavailable" || result.State == "invalid_configuration" {
			status = http.StatusServiceUnavailable
		}
		server.writeJSON(response, request, status, map[string]any{
			"apiVersion":    APIVersion,
			"kind":          "ServiceHealth",
			"correlationId": correlationID,
			"result":        result,
		})
		return
	}
	server.writeError(response, request, http.StatusNotFound, "NOT_FOUND", "The requested service resource does not exist.", correlationID)
}

func (server *Server) writeAggregateHealth(response http.ResponseWriter, request *http.Request, correlationID string) {
	results := make([]ServiceHealth, len(server.registry.Services))
	semaphore := make(chan struct{}, server.maxConcurrency)
	var wait sync.WaitGroup
	for index, service := range server.registry.Services {
		wait.Add(1)
		go func(index int, service Service) {
			defer wait.Done()
			semaphore <- struct{}{}
			defer func() { <-semaphore }()
			server.probeRequests.Add(1)
			result := server.prober.Probe(request.Context(), service, correlationID)
			if result.State != "ready" && result.State != "unconfigured" {
				server.probeFailures.Add(1)
			}
			results[index] = result
		}(index, service)
	}
	wait.Wait()
	counts := map[string]int{}
	for _, result := range results {
		counts[result.State]++
	}
	state := "ready"
	if counts["unavailable"] > 0 || counts["invalid_configuration"] > 0 {
		state = "degraded"
	} else if counts["unconfigured"] > 0 {
		state = "incomplete"
	}
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "SuiteHealth",
		"correlationId": correlationID,
		"state":         state,
		"counts":        counts,
		"items":         results,
		"generatedAt":   time.Now().UTC(),
	})
}

func (server *Server) writeTopology(response http.ResponseWriter, request *http.Request, correlationID string) {
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "SuiteTopology",
		"correlationId": correlationID,
		"nodes":         server.registry.Services,
		"edges":         server.registry.Edges,
	})
}

func (server *Server) writeContracts(response http.ResponseWriter, request *http.Request, correlationID string) {
	items := make([]map[string]any, 0, len(server.registry.Services))
	for _, service := range server.registry.Services {
		items = append(items, map[string]any{
			"serviceId":  service.ID,
			"repository": service.Repository,
			"path":       service.Contract.Path,
			"version":    service.Contract.Version,
		})
	}
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "ServiceContractList",
		"correlationId": correlationID,
		"schema":        server.registry.ContractSchema,
		"items":         items,
	})
}

var (
	gitSHA      = regexp.MustCompile(`^[0-9a-f]{40}$`)
	imageDigest = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
)

func releaseReadback(service Service) map[string]any {
	source := strings.TrimSpace(os.Getenv(service.Release.SourceRevisionEnv))
	digest := strings.TrimSpace(os.Getenv(service.Release.ImageDigestEnv))
	state := "configured"
	if source == "" && digest == "" {
		state = "unconfigured"
	} else if source == "" || digest == "" {
		state = "partial"
	} else if !gitSHA.MatchString(source) || !imageDigest.MatchString(digest) {
		state = "invalid"
	}
	result := map[string]any{"state": state, "immutableImageRequired": true}
	if gitSHA.MatchString(source) {
		result["sourceRevision"] = source
	}
	if imageDigest.MatchString(digest) {
		result["imageDigest"] = digest
	}
	return result
}

func (server *Server) writeReleases(response http.ResponseWriter, request *http.Request, correlationID string) {
	items := make([]map[string]any, 0, len(server.registry.Services))
	for _, service := range server.registry.Services {
		items = append(items, map[string]any{
			"serviceId":  service.ID,
			"repository": service.Repository,
			"release":    releaseReadback(service),
		})
	}
	server.writeJSON(response, request, http.StatusOK, map[string]any{
		"apiVersion":    APIVersion,
		"kind":          "ReleaseIdentityList",
		"correlationId": correlationID,
		"items":         items,
	})
}

func (server *Server) writeOpenAPI(response http.ResponseWriter, request *http.Request) {
	if len(server.openAPI) == 0 {
		server.writeError(response, request, http.StatusNotFound, "OPENAPI_UNAVAILABLE", "OpenAPI is not configured.", response.Header().Get("X-Correlation-ID"))
		return
	}
	response.Header().Set("Content-Type", "application/json; charset=utf-8")
	response.WriteHeader(http.StatusOK)
	if request.Method != http.MethodHead {
		_, _ = response.Write(server.openAPI)
	}
}

func (server *Server) writeMetrics(response http.ResponseWriter, request *http.Request) {
	configured := 0
	for _, service := range server.registry.Services {
		if strings.TrimSpace(os.Getenv(service.BaseURLEnv)) != "" {
			configured++
		}
	}
	response.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	response.WriteHeader(http.StatusOK)
	if request.Method == http.MethodHead {
		return
	}
	_, _ = fmt.Fprintf(response, "# HELP codestra_observability_control_api_up Whether the control API process is up.\n")
	_, _ = fmt.Fprintf(response, "# TYPE codestra_observability_control_api_up gauge\n")
	_, _ = fmt.Fprintf(response, "codestra_observability_control_api_up 1\n")
	_, _ = fmt.Fprintf(response, "# HELP codestra_observability_control_api_registry_services Number of registered suite services.\n")
	_, _ = fmt.Fprintf(response, "# TYPE codestra_observability_control_api_registry_services gauge\n")
	_, _ = fmt.Fprintf(response, "codestra_observability_control_api_registry_services %d\n", len(server.registry.Services))
	_, _ = fmt.Fprintf(response, "# HELP codestra_observability_control_api_configured_services Number of services with a configured base URL.\n")
	_, _ = fmt.Fprintf(response, "# TYPE codestra_observability_control_api_configured_services gauge\n")
	_, _ = fmt.Fprintf(response, "codestra_observability_control_api_configured_services %d\n", configured)
	_, _ = fmt.Fprintf(response, "# HELP codestra_observability_control_api_probe_requests_total Upstream probe requests attempted.\n")
	_, _ = fmt.Fprintf(response, "# TYPE codestra_observability_control_api_probe_requests_total counter\n")
	_, _ = fmt.Fprintf(response, "codestra_observability_control_api_probe_requests_total %d\n", server.probeRequests.Load())
	_, _ = fmt.Fprintf(response, "# HELP codestra_observability_control_api_probe_failures_total Upstream probe requests with unavailable or invalid results.\n")
	_, _ = fmt.Fprintf(response, "# TYPE codestra_observability_control_api_probe_failures_total counter\n")
	_, _ = fmt.Fprintf(response, "codestra_observability_control_api_probe_failures_total %d\n", server.probeFailures.Load())
}

func (server *Server) service(id string) (Service, bool) {
	for _, service := range server.registry.Services {
		if service.ID == id {
			return service, true
		}
	}
	return Service{}, false
}

func setCommonHeaders(response http.ResponseWriter, correlationID string) {
	response.Header().Set("Cache-Control", "no-store, max-age=0")
	response.Header().Set("Pragma", "no-cache")
	response.Header().Set("Referrer-Policy", "no-referrer")
	response.Header().Set("X-Content-Type-Options", "nosniff")
	response.Header().Set("X-Frame-Options", "DENY")
	response.Header().Set("X-Correlation-ID", correlationID)
}

func correlationID(value string) string {
	value = strings.TrimSpace(value)
	if correlationPattern.MatchString(value) {
		return value
	}
	buffer := make([]byte, 16)
	if _, err := rand.Read(buffer); err == nil {
		return hex.EncodeToString(buffer)
	}
	return fmt.Sprintf("fallback-%d", time.Now().UnixNano())
}

func (server *Server) writeError(response http.ResponseWriter, request *http.Request, status int, code, message, correlationID string) {
	server.writeJSON(response, request, status, errorResponse{
		APIVersion:    APIVersion,
		Kind:          "Problem",
		Code:          code,
		Message:       message,
		CorrelationID: correlationID,
	})
}

func (server *Server) writeJSON(response http.ResponseWriter, request *http.Request, status int, value any) {
	response.Header().Set("Content-Type", "application/json; charset=utf-8")
	response.WriteHeader(status)
	if request.Method == http.MethodHead {
		return
	}
	encoder := json.NewEncoder(response)
	encoder.SetEscapeHTML(true)
	_ = encoder.Encode(value)
}

func SortedServiceIDs(registry Registry) []string {
	ids := make([]string, 0, len(registry.Services))
	for _, service := range registry.Services {
		ids = append(ids, service.ID)
	}
	sort.Strings(ids)
	return ids
}
