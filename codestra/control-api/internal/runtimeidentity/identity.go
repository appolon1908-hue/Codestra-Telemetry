package runtimeidentity

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

var (
	sourcePattern = regexp.MustCompile(`^[0-9a-f]{40}$`)
	digestPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
	imagePattern  = regexp.MustCompile(`^ghcr\.io/appolon1908-hue/codestra-telemetry-control-api@(sha256:[0-9a-f]{64})$`)
)

const embeddedSourcePath = "/usr/share/codestra/source-revision"

func ValidateValues(source, bakedSource, digest, image, embeddedSource string) error {
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

func ValidateEnvironment() error {
	embedded, err := os.ReadFile(embeddedSourcePath)
	if err != nil {
		return fmt.Errorf("embedded source identity is unavailable")
	}
	return ValidateValues(
		strings.TrimSpace(os.Getenv("CODESTRA_SOURCE_SHA")),
		strings.TrimSpace(os.Getenv("CODESTRA_IMAGE_SOURCE_SHA")),
		strings.TrimSpace(os.Getenv("CODESTRA_IMAGE_DIGEST")),
		strings.TrimSpace(os.Getenv("CODESTRA_CONTROL_API_IMAGE")),
		strings.TrimSpace(string(embedded)),
	)
}
