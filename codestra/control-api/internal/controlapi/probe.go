package controlapi

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"strings"
	"time"
)

type CheckResult struct {
	State      string `json:"state"`
	StatusCode int    `json:"statusCode,omitempty"`
	DurationMS int64  `json:"durationMs"`
	Reason     string `json:"reason,omitempty"`
}

type ServiceHealth struct {
	ServiceID  string      `json:"serviceId"`
	Configured bool        `json:"configured"`
	State      string      `json:"state"`
	Health     CheckResult `json:"health"`
	Readiness  CheckResult `json:"readiness"`
	CheckedAt  time.Time   `json:"checkedAt"`
}

type Prober interface {
	Probe(ctx context.Context, service Service, correlationID string) ServiceHealth
}

type HTTPProber struct{}

func (HTTPProber) Probe(ctx context.Context, service Service, correlationID string) ServiceHealth {
	checkedAt := time.Now().UTC()
	baseValue := strings.TrimSpace(os.Getenv(service.BaseURLEnv))
	if baseValue == "" {
		return ServiceHealth{
			ServiceID:  service.ID,
			Configured: false,
			State:      "unconfigured",
			Health:     CheckResult{State: "unknown", Reason: "missing_base_url"},
			Readiness:  CheckResult{State: "unknown", Reason: "missing_base_url"},
			CheckedAt:  checkedAt,
		}
	}
	baseURL, err := validateBaseURL(baseValue)
	if err != nil {
		return ServiceHealth{
			ServiceID:  service.ID,
			Configured: true,
			State:      "invalid_configuration",
			Health:     CheckResult{State: "unknown", Reason: "invalid_base_url"},
			Readiness:  CheckResult{State: "unknown", Reason: "invalid_base_url"},
			CheckedAt:  checkedAt,
		}
	}
	client, err := clientFor(service)
	if err != nil {
		return ServiceHealth{
			ServiceID:  service.ID,
			Configured: true,
			State:      "invalid_configuration",
			Health:     CheckResult{State: "unknown", Reason: "invalid_transport_configuration"},
			Readiness:  CheckResult{State: "unknown", Reason: "invalid_transport_configuration"},
			CheckedAt:  checkedAt,
		}
	}
	token, err := bearerToken(service.Auth.BearerTokenFileEnv)
	if err != nil {
		return ServiceHealth{
			ServiceID:  service.ID,
			Configured: true,
			State:      "invalid_configuration",
			Health:     CheckResult{State: "unknown", Reason: "credential_file_unavailable"},
			Readiness:  CheckResult{State: "unknown", Reason: "credential_file_unavailable"},
			CheckedAt:  checkedAt,
		}
	}

	timeout := time.Duration(service.TimeoutMS) * time.Millisecond
	health := executeCheck(ctx, client, baseURL, service.Health, token, correlationID, timeout)
	readiness := executeCheck(ctx, client, baseURL, service.Readiness, token, correlationID, timeout)
	state := "ready"
	if health.State != "up" {
		state = "unavailable"
	} else if readiness.State != "up" {
		state = "degraded"
	}
	return ServiceHealth{
		ServiceID:  service.ID,
		Configured: true,
		State:      state,
		Health:     health,
		Readiness:  readiness,
		CheckedAt:  checkedAt,
	}
}

func validateBaseURL(raw string) (*url.URL, error) {
	parsed, err := url.Parse(raw)
	if err != nil {
		return nil, err
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, errors.New("only http and https are supported")
	}
	if parsed.Host == "" || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, errors.New("base URL must contain only scheme, host, port, and optional path")
	}
	return parsed, nil
}

func clientFor(service Service) (*http.Client, error) {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = http.ProxyFromEnvironment
	transport.MaxIdleConns = 32
	transport.MaxIdleConnsPerHost = 4
	transport.IdleConnTimeout = 30 * time.Second
	transport.TLSHandshakeTimeout = 3 * time.Second
	transport.ResponseHeaderTimeout = time.Duration(service.TimeoutMS) * time.Millisecond

	tlsConfig := &tls.Config{MinVersion: tls.VersionTLS12}
	if env := service.Auth.CAFileEnv; env != "" {
		file := strings.TrimSpace(os.Getenv(env))
		if file == "" {
			return nil, fmt.Errorf("%s is not configured", env)
		}
		pem, err := os.ReadFile(file)
		if err != nil {
			return nil, err
		}
		pool, err := x509.SystemCertPool()
		if err != nil || pool == nil {
			pool = x509.NewCertPool()
		}
		if !pool.AppendCertsFromPEM(pem) {
			return nil, errors.New("CA file does not contain a certificate")
		}
		tlsConfig.RootCAs = pool
	}
	if service.Auth.ClientCertFileEnv != "" {
		certPath := strings.TrimSpace(os.Getenv(service.Auth.ClientCertFileEnv))
		keyPath := strings.TrimSpace(os.Getenv(service.Auth.ClientKeyFileEnv))
		if certPath == "" || keyPath == "" {
			return nil, errors.New("mTLS certificate and key files are required")
		}
		certificate, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			return nil, err
		}
		tlsConfig.Certificates = []tls.Certificate{certificate}
	}
	transport.TLSClientConfig = tlsConfig

	return &http.Client{
		Transport: transport,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}, nil
}

func bearerToken(envName string) (string, error) {
	if envName == "" {
		return "", nil
	}
	file := strings.TrimSpace(os.Getenv(envName))
	if file == "" {
		return "", fmt.Errorf("%s is not configured", envName)
	}
	content, err := os.ReadFile(file)
	if err != nil {
		return "", err
	}
	if len(content) > 64*1024 {
		return "", errors.New("bearer token file exceeds 64 KiB")
	}
	token := strings.TrimSpace(string(content))
	if token == "" || strings.ContainsAny(token, "\r\n") {
		return "", errors.New("bearer token is empty or malformed")
	}
	return token, nil
}

func executeCheck(
	parent context.Context,
	client *http.Client,
	baseURL *url.URL,
	probe ProbeConfig,
	token string,
	correlationID string,
	timeout time.Duration,
) CheckResult {
	started := time.Now()
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()

	endpoint := *baseURL
	endpoint.Path = path.Join(strings.TrimSuffix(baseURL.Path, "/"), probe.Path)
	if strings.HasSuffix(probe.Path, "/") && !strings.HasSuffix(endpoint.Path, "/") {
		endpoint.Path += "/"
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return checkFailure(started, "request_construction_failed")
	}
	request.Header.Set("Accept", "application/json, text/plain;q=0.9, */*;q=0.1")
	request.Header.Set("User-Agent", "codestra-observability-control-api/1.0")
	request.Header.Set("X-Correlation-ID", correlationID)
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response, err := client.Do(request)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return checkFailure(started, "timeout")
		}
		return checkFailure(started, "upstream_unreachable")
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 4096))

	result := CheckResult{StatusCode: response.StatusCode, DurationMS: time.Since(started).Milliseconds()}
	for _, accepted := range probe.AcceptedStatuses {
		if response.StatusCode == accepted {
			result.State = "up"
			return result
		}
	}
	result.State = "down"
	result.Reason = "unexpected_status"
	return result
}

func checkFailure(started time.Time, reason string) CheckResult {
	return CheckResult{State: "down", DurationMS: time.Since(started).Milliseconds(), Reason: reason}
}
