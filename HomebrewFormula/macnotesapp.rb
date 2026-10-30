require "formula"

$pkg_version = "v0.8.3"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/#{$pkg_group}/#{$pkg_repo}/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "c8cb7d88cf050ff073400f79706c8378ae11a19c9e93fa157883132d3cb31a68"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
