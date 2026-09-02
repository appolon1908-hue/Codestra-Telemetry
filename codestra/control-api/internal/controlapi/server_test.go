package controlapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func newTestServer(t *testing.T, authMode string) (*Server, string) {
	t.Helper()
	tokenFile := filepath.Join(t.TempDir(), "token")
	if err := os.WriteFile(tokenFile, []byte("test-control-token\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	server, err := NewServer(ServerOptions{
		Registry:        validRegistry(),
		AuthMode:        authMode,
		BearerTokenFile: tokenFile,
		OpenAPI:         []byte(`{"openapi":"3.1.0"}`),
	})
	if err != nil {
		t.Fatal(err)
	}
	return server, tokenFile
}

func authorizedRequest(t *testing.T, method, target string) *http.Request {
	t.Helper()
	request := httptest.NewRequest(method, target, nil)
	request.Header.Set("Authorization", "Bearer test-control-token")
	return request
}

func TestControlAPIRequiresAuthentication(t *testing.T) {
	server, _ := newTestServer(t, "required")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/api/v1/services", nil))
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}
}

func TestControlAPIIsReadOnly(t *testing.T) {
	server, _ := newTestServer(t, "required")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, authorizedRequest(t, http.MethodPost, "/api/v1/services"))
	if response.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405, got %d", response.Code)
	}
	if response.Header().Get("Allow") != "GET, HEAD, OPTIONS" {
		t.Fatalf("unexpected Allow header: %q", response.Header().Get("Allow"))
	}
}

func TestServiceHealthDiscardsUpstreamBody(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.Header.Get("X-Correlation-ID") != "corr-123" {
			t.Errorf("correlation ID not propagated")
		}
		response.WriteHeader(http.StatusOK)
		_, _ = response.Write([]byte(`{"secret":"must-not-escape"}`))
	}))
	defer upstream.Close()
	t.Setenv("CODESTRA_PROMETHEUS_URL", upstream.URL)

	server, _ := newTestServer(t, "required")
	request := authorizedRequest(t, http.MethodGet, "/api/v1/services/prometheus/health")
	request.Header.Set("X-Correlation-ID", "corr-123")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
	if strings.Contains(response.Body.String(), "must-not-escape") {
		t.Fatal("upstream response body escaped into the control API")
	}
	var document map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &document); err != nil {
		t.Fatal(err)
	}
	if document["correlationId"] != "corr-123" {
		t.Fatalf("correlation ID missing from response: %#v", document)
	}
}

func TestReleaseReadbackRejectsMalformedIdentity(t *testing.T) {
	t.Setenv("CODESTRA_PROMETHEUS_SOURCE_REVISION", "main")
	t.Setenv("CODESTRA_PROMETHEUS_IMAGE_DIGEST", "latest")
	result := releaseReadback(validRegistry().Services[0])
	if result["state"] != "invalid" {
		t.Fatalf("expected invalid release state, got %#v", result)
	}
	if _, ok := result["sourceRevision"]; ok {
		t.Fatal("malformed source revision exposed")
	}
	if _, ok := result["imageDigest"]; ok {
		t.Fatal("malformed image digest exposed")
	}
}

func TestHealthAndReadinessRemainUnauthenticated(t *testing.T) {
	server, _ := newTestServer(t, "required")
	for _, route := range []string{"/healthz", "/readyz"} {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, route, nil))
		if response.Code != http.StatusOK {
			t.Fatalf("%s expected 200, got %d", route, response.Code)
		}
	}
}
