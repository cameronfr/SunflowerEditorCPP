# SunflowerEditorCPP

Using SunflowerEditor, you can see the values in your C++ code in realtime. Example:

[](images/example1.png)

SunflowerEditor transforms your C++ code with libclang and compiles it with cppyy. It currently supports seeing the values of printf's inline, but is extremely extensible! 

Contributions extremely welcome! Talk to us in the [Discord](https://discord.gg/zYmm5JuHkW)

The intention is to be a C++ version of [SunflowerEditor](https://github.com/cameronfr/SunflowerEditor)

# Installation and Tutorial

```
pip install cppyy
brew install llvm@14
```

and

```
cd sunflowereditor-vscode
yarn add zeromq electron-rebuild
yarn electron-rebuild -v 19.0.17 zeromq
yarn install
```

Then start the extension by opening `sunflowereditor-vscode` in VSCode, and clicking run. In that editor, open `SunflowerEditorTesting.cpp` to see the annotations.

Finally, edit `llvmDir` on line 8 of `main.py` to match your installation and run with `python3 main.py`. (Running with Jupyter is recommended, however). You should see realtime annotations as in the example image above.

You can edit `SunflowerEditorTesting.cpp`, and rerun the following cell to recompile and rerun the C++!
```
_, runtimeTest = defineInNewNs(f"""
  {includeFile(editorRuntimeDir, fileToRun, runtimeNsName=editorRuntimeNsName, transform=True)}
""")
runtimeTest.doStuff()
for i in range(100):
  runtimeTest.doStuff2()
  time.sleep(0.05)
```

Running into issues? Happy to help in the [Discord](https://discord.gg/zYmm5JuHkW)!


