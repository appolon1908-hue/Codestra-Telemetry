package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
	"syscall"
)

var (
	sourcePattern = regexp.MustCompile(`^[0-9a-f]{40}$`)
	digestPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
	imagePattern  = regexp.MustCompile(`^ghcr\.io/appolon1908-hue/codestra-telemetry-opentelemetry@(sha256:[0-9a-f]{64})$`)
)

const embeddedSourcePath = "/usr/share/codestra/source-revision"

func validateIdentity(source, bakedSource, digest, image, embeddedSource string) error {
	if !sourcePattern.MatchString(source) || !sourcePattern.MatchString(bakedSource) || !sourcePattern.MatchString(embeddedSource) {
		return fmt.Errorf("source identity is malformed")
	}
	if source != bakedSource || source != embeddedSource {
		return fmt.Errorf("runtime source identity differs from the immutable image")
	}
	match := imagePattern.FindStringSubmatch(image)
	if !digestPattern.MatchString(digest) || len(match) != 2 || match[1] != digest {
		return fmt.Errorf("runtime image identity is malformed or inconsistent")
	}
	return nil
}

func main() {
	embedded, err := os.ReadFile(embeddedSourcePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "collector startup identity validation failed")
		os.Exit(78)
	}
	if err := validateIdentity(
		strings.TrimSpace(os.Getenv("CODESTRA_SOURCE_SHA")),
		strings.TrimSpace(os.Getenv("CODESTRA_IMAGE_SOURCE_SHA")),
		strings.TrimSpace(os.Getenv("CODESTRA_IMAGE_DIGEST")),
		strings.TrimSpace(os.Getenv("CODESTRA_OTELCOL_IMAGE")),
		strings.TrimSpace(string(embedded)),
	); err != nil {
		fmt.Fprintln(os.Stderr, "collector startup identity validation failed")
		os.Exit(78)
	}
	if err := syscall.Exec("/otelcol-contrib", append([]string{"/otelcol-contrib"}, os.Args[1:]...), os.Environ()); err != nil {
		fmt.Fprintln(os.Stderr, "collector executable handoff failed")
		os.Exit(126)
	}
}
