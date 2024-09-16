require "formula"

$pkg_version = "v0.7.0"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/#{$pkg_group}/#{$pkg_repo}/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "2c71126f10aad7505d39c24cba46ce996c6d63d66c1653b8c679c28519b3259c"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
