require "formula"

$pkg_version = "v0.8.1"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/#{$pkg_group}/#{$pkg_repo}/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "0c55488ab737f5e566d45f96dd8e86e893e9ebe4398b6dd19008f917c4eebc6e"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
