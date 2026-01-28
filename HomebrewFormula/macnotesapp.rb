require "formula"

$pkg_version = "v0.8.1"
$pkg_group = "RhetTbull"
$pkg_repo = "macnotesapp"

class Macnotesapp < Formula
  url "https://github.com/#{$pkg_group}/#{$pkg_repo}/releases/download/#{$pkg_version}/notes.zip"
  version $pkg_version
  homepage "https://github.com/#{$pkg_group}/#{$pkg_repo}"
  desc "cli tool to interact with MacOS Notes"
  sha256 "fdc1bb661dacdec719e7732d7e9c113c8412a010a7159b80dcdc604b711be331"

  depends_on "python@3.12"

  def install
    bin.install "notes"
  end
end
