package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/appolon1908-hue/Codestra-Telemetry/codestra/control-api/internal/controlapi"
)

func main() {
	logger := log.New(os.Stdout, "", 0)
	registryPath := envOrDefault("CODESTRA_CONTROL_API_REGISTRY_FILE", "config/services.json")
	openAPIPath := envOrDefault("CODESTRA_CONTROL_API_OPENAPI_FILE", "openapi.json")
	listenAddress := envOrDefault("CODESTRA_CONTROL_API_LISTEN_ADDRESS", "127.0.0.1:8090")
	authMode := envOrDefault("CODESTRA_CONTROL_API_AUTH_MODE", "required")
	tokenFile := strings.TrimSpace(os.Getenv("CODESTRA_CONTROL_API_BEARER_TOKEN_FILE"))
	maxConcurrency := envInt("CODESTRA_CONTROL_API_MAX_CONCURRENCY", 6)

	registry, err := controlapi.LoadRegistry(registryPath)
	if err != nil {
		fatal(logger, "registry_invalid", err)
	}
	openAPI, err := os.ReadFile(openAPIPath)
	if err != nil {
		fatal(logger, "openapi_unavailable", err)
	}
	serverHandler, err := controlapi.NewServer(controlapi.ServerOptions{
		Registry:        registry,
		OpenAPI:         openAPI,
		AuthMode:        authMode,
		BearerTokenFile: tokenFile,
		MaxConcurrency:  maxConcurrency,
	})
	if err != nil {
		fatal(logger, "server_configuration_invalid", err)
	}

	httpServer := &http.Server{
		Addr:              listenAddress,
		Handler:           serverHandler.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	shutdownContext, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go func() {
		<-shutdownContext.Done()
		context, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = httpServer.Shutdown(context)
	}()

	info(logger, "server_start", map[string]any{
		"listenAddress": listenAddress,
		"authMode":      authMode,
		"services":      len(registry.Services),
	})
	if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fatal(logger, "server_failed", err)
	}
	info(logger, "server_stop", map[string]any{"state": "clean"})
}

func envOrDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envInt(name string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func info(logger *log.Logger, event string, fields map[string]any) {
	fields["event"] = event
	fields["timestamp"] = time.Now().UTC().Format(time.RFC3339Nano)
	payload, _ := json.Marshal(fields)
	logger.Print(string(payload))
}

func fatal(logger *log.Logger, event string, err error) {
	payload, _ := json.Marshal(map[string]any{
		"event":     event,
		"error":     err.Error(),
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
	})
	logger.Fatal(string(payload))
}
