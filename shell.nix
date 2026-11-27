{ pkgs ? import <nixpkgs> { } }:

with pkgs;

python3.pkgs.buildPythonApplication rec {

  python = python3;

  name = "smoopi";

  nativeBuildInputs = with python.pkgs; [
    kivy
    aiofiles
    pyserial

    xclip
  ];
}
