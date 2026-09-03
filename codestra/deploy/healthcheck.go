package main

import (
	"io"
	"net/http"
	"os"
	"time"
)

const defaultURL = "http://127.0.0.1:13133/"

func main() {
	client := &http.Client{
		Timeout: 5 * time.Second,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	request, err := http.NewRequest(http.MethodGet, defaultURL, nil)
	if err != nil {
		os.Exit(1)
	}
	resp, err := client.Do(request)
	if err != nil {
		os.Exit(1)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4096))

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		os.Exit(1)
	}
}
