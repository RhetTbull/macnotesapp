require "formula"

$pkg_version = "v0.6.1"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/RhetTbull/macnotesapp/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "7af6d7373add289aeaf435a211cbda39f689708be5be5d09c737bf16307e92bf"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
