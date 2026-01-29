require "formula"

$pkg_version = "v0.8.2"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/#{$pkg_group}/#{$pkg_repo}/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "e7613f2c471ebf49b877524372a28d16c4633ce209e174fbb03f2b8ecd741fbb"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
