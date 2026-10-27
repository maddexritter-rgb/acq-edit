# Private artifacts are fetched through GitHub's API at download time only.
# Uses Homebrew's credentials (including Workbrew Secret Brew Configuration).
class AcqPrivateRelease < CurlDownloadStrategy
  def initialize(url, name, version, **meta)
    super
    parts = url.match(%r{\Ahttps://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/([^/]+)\z})
    raise CurlDownloadStrategyError.new(url, "Invalid ACQ release URL") unless parts
    @account, @repository, @release_tag, @asset_name = parts.captures
  end

  private

  def release_asset
    @release_asset ||= begin
      response = GitHub::API.open_rest(
        GitHub.url_to("repos", @account, @repository, "releases", "tags", @release_tag),
        scopes: ["repo"],
      )
      match = response.fetch("assets").find { |entry| entry.fetch("name") == @asset_name }
      raise CurlDownloadStrategyError.new(url, "Release asset unavailable; check repository access") unless match
      match
    end
  end

  def resolve_url_basename_time_file_size(_url, timeout: nil)
    item = release_asset
    [item.fetch("url"), @asset_name, Time.parse(item.fetch("updated_at")),
     item.fetch("size"), item.fetch("content_type"), false]
  end

  def _fetch(url:, resolved_url:, timeout:)
    credential = GitHub::API.credentials
    raise CurlDownloadStrategyError.new(url, "Sign into GitHub or configure the Workbrew GitHub API token") if credential.empty?
    headers = ["Accept: application/octet-stream", "Authorization: Bearer #{credential}"]
    curl_download(resolved_url, to: temporary_path, try_partial: @try_partial, timeout: timeout, header: headers)
  end
end
