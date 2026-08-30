package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const defaultURL = "http://127.0.0.1:13133/"

func main() {
	url := os.Getenv("OTELCOL_HEALTHCHECK_URL")
	if url == "" {
		url = defaultURL
	}

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url) // #nosec G107 -- operator-controlled local health endpoint.
	if err != nil {
		fmt.Fprintf(os.Stderr, "collector health request failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4096))

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		fmt.Fprintf(os.Stderr, "collector health returned HTTP %d\n", resp.StatusCode)
		os.Exit(1)
	}
}
