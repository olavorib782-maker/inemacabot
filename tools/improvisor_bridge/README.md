# Ponte headless do Impro-Visor

Protótipo Java isolado para converter um leadsheet `.ls` em MusicXML ou gerar
uma linha de guide tones sobre sua harmonia. As duas operações usam o parser e
o exportador oficiais do Impro-Visor. A ponte não inicializa `imp.ImproVisor`,
não cria `Notate` e não usa MIDI.

A ponte carrega `My.prefs`, `My.voc` e os estilos antes de criar o `Score`, pois
o modelo do Impro-Visor depende desses valores padrão. A carga de `My.voc`
reutiliza `Tokenizer` e `Advisor.setRules()` sem usar o `LoadAdviceCommand`, que
constrói um diálogo Swing. Na primeira execução, os métodos
estáticos oficiais podem preparar `impro-visor-version-10.2-files` sob
`user.home`; a classe `imp.ImproVisor` é usada somente para resolver caminhos e
não é instanciada. Use um `user.home` isolado e
gravável em servidor.

## Dependências

- Um JDK com `java` e `javac`. Java 8 ou mais recente; o Impro-Visor 10.2
  recomenda Java 8.
- Uma cópia separada do repositório Impro-Visor:
  <https://github.com/Impro-Visor/Impro-Visor>
- As classes compiladas do Impro-Visor em `<Impro-Visor>\build` e os JARs em
  `<Impro-Visor>\lib\*`. Esse foi o classpath validado no protótipo.

Não clone o Impro-Visor dentro do InemacaBot. Nos exemplos abaixo, defina
`IMPROVISOR_HOME` como o caminho absoluto do clone e compile o projeto para que
`$env:IMPROVISOR_HOME\build` contenha as classes Java. Consulte o `build.xml` do
Impro-Visor para preparar esse build. A validação deste protótipo não usou
`improvisor.jar` como classpath principal.

Exemplo de clone separado:

```powershell
git clone https://github.com/Impro-Visor/Impro-Visor.git C:\projetos\Impro-Visor
```

## Compilar

PowerShell, a partir da raiz do InemacaBot:

```powershell
$env:IMPROVISOR_HOME = 'C:\projetos\Impro-Visor'
$improvisorClasspath = "$env:IMPROVISOR_HOME\build;$env:IMPROVISOR_HOME\lib\*"

javac `
  -cp $improvisorClasspath `
  -d tools\improvisor_bridge\build `
  tools\improvisor_bridge\ImproVisorBridge.java
```

O diretório `tools\improvisor_bridge\build` é uma saída local ignorada pelo
Git. Ele deve conter `ImproVisorBridge.class` depois da compilação.

No Linux, substitua `;` por `:` no classpath.

## Executar

### Converter um leadsheet

PowerShell:

```powershell
$runtimeClasspath = "tools\improvisor_bridge\build;$env:IMPROVISOR_HOME\build;$env:IMPROVISOR_HOME\lib\*"
$improvisorUserHome = Join-Path $env:LOCALAPPDATA 'InemacaBot\improvisor-home'

java `
  -Djava.awt.headless=true `
  "-Duser.home=$improvisorUserHome" `
  -Xmx256m `
  -cp $runtimeClasspath `
  ImproVisorBridge `
  "$env:IMPROVISOR_HOME\leadsheets\arquivo-valido.ls" `
  "tools\improvisor_bridge\output.xml"
```

O formato original com dois argumentos continua sendo a operação de conversão
simples:

```text
ImproVisorBridge <input.ls> <output.xml>
```

### Gerar guide tones

```powershell
java `
  -Djava.awt.headless=true `
  "-Duser.home=$improvisorUserHome" `
  -Xmx256m `
  -cp $runtimeClasspath `
  ImproVisorBridge `
  guidetones `
  "input.ls" `
  "guide-tones.xml"
```

A operação carrega a harmonia do `.ls`, gera uma única linha monofônica e
substitui somente as partes melódicas do `Score` antes de exportar. Os acordes,
métrica e demais metadados permanecem no score.

Os parâmetros fixos deste primeiro protótipo são: direção sem preferência,
grau inicial 3, tessitura MIDI 55 a 79, uma nota por acorde, uma linha, somente
chord tones e repetição consecutiva de altura desabilitada. A sintaxe é:

```text
ImproVisorBridge guidetones <input.ls> <output.xml>
```

Os caminhos são argumentos distintos do processo, não texto para um shell
interpretar. A integração em `improvisor_client.py` usa
`asyncio.create_subprocess_exec` sem shell, aplica timeout e valida o MusicXML.
O `ImproVisorClient` suporta tanto a conversão legada quanto
`generate_guidetones()`, mantendo esta bridge como a fronteira com o Java e o
Impro-Visor.

A ponte retorna `0` em caso de sucesso, `1` em falha de leitura/conversão e `2`
para uso incorreto ou ausência de `-Djava.awt.headless=true`.

## Teste manual

Escolha um `.ls` existente no clone e execute o comando acima. Em seguida:

```powershell
if ($LASTEXITCODE -ne 0) { throw 'Conversao falhou.' }
if (-not (Test-Path tools\improvisor_bridge\output.xml -PathType Leaf)) {
  throw 'output.xml nao foi criado.'
}

$xml = [xml](Get-Content tools\improvisor_bridge\output.xml -Raw)
(Get-Item tools\improvisor_bridge\output.xml).Length
```

O cast para `[xml]` confirma que a saída é XML bem formado. A propriedade
`Length` informa o tamanho gerado em bytes.
