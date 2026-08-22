# Assinatura digital do instalador (SignPath Foundation)

## Como funciona (e o que só você pode fazer)

A [SignPath Foundation](https://signpath.org) oferece **assinatura de código
gratuita para projetos open source**. Importante entender: ela **não entrega um
arquivo de certificado** — o certificado fica com a fundação, e o seu instalador
é assinado **dentro do serviço deles**, integrado ao GitHub Actions. O
certificado sai em nome de "SignPath Foundation", com o seu projeto
identificado nos atributos.

A inscrição envolve **criar uma conta, aceitar termos legais e passar por uma
análise humana da fundação** — por isso essa parte é sua. Todo o resto (o
pipeline que assina automaticamente) **já está pronto neste repositório** e
ativa sozinho quando você configurar os secrets (passo 4).

## O que o projeto já cumpre (preparado)

- ✅ Repositório público no GitHub: `github.com/cartaproale/PySusNoCode`
- ✅ Licença open source aprovada pela OSI (MIT, arquivo `LICENSE`)
- ✅ **Instalador compilado 100% pelo GitHub Actions a partir do código-fonte
  público** (requisito central da fundação — nada de uploads manuais); veja
  `.github/workflows/build-installer.yml`
- ✅ Releases automatizadas com artefatos rastreáveis por tag
- ✅ Passos de assinatura já embutidos no workflow (dormentes até os secrets
  existirem)

## Expectativa honesta

A fundação avalia a **maturidade do projeto** (tempo de vida, atividade,
comunidade, downloads). O PySusNoCode é novo — é possível que a resposta seja
"ainda não". Nesse caso: continue lançando versões normalmente e reaplique
quando o projeto tiver histórico e usuários. Alternativas pagas, em seu próprio
nome (sem análise de maturidade): certificado **Certum Open Source Code
Signing** (~US$ 40–70/ano, assinatura local com `signtool`) ou **Azure Trusted
Signing**. E lembre: mesmo assinado, o SmartScreen ainda constrói reputação com
o volume de downloads — a assinatura remove o "Editor desconhecido" e acelera
muito esse processo, mas o aviso azul pode aparecer nos primeiros dias.

## Passo a passo da inscrição (sua parte, ~15 minutos)

1. **Inscreva o projeto**: acesse https://signpath.org e use o formulário
   *Apply for free open source code signing*. Informe:
   - URL do repositório: `https://github.com/cartaproale/PySusNoCode`
   - Descrição curta (em inglês; há um resumo pronto no fim do `README.md`)
   - Seu papel: mantenedor/owner do repositório
2. **Aguarde a análise** da fundação (e-mail). Aprovado, você recebe acesso a
   uma organização no https://app.signpath.io.
3. **Configure no SignPath** (painel deles, guiado):
   - Conecte o repositório GitHub (instale o **SignPath GitHub App** quando
     solicitado);
   - Crie o **Project** para o PySusNoCode com uma *artifact configuration*
     do tipo **PE file** (o `.exe` do instalador);
   - Crie/confirme a **Signing Policy** de release (ex.: `release-signing`);
   - Gere um **API token** de CI (menu do usuário → *API tokens*).
4. **Configure os 4 secrets no GitHub**: no repositório →
   *Settings → Secrets and variables → Actions → New repository secret*:

   | Secret | Valor (do painel SignPath) |
   |---|---|
   | `SIGNPATH_API_TOKEN` | o API token gerado |
   | `SIGNPATH_ORGANIZATION_ID` | ID da organização (GUID) |
   | `SIGNPATH_PROJECT_SLUG` | slug do projeto (ex.: `PySusNoCode`) |
   | `SIGNPATH_SIGNING_POLICY_SLUG` | slug da policy (ex.: `release-signing`) |

5. **Lance a próxima versão normalmente** (`git tag vX.Y.Z && git push origin
   vX.Y.Z`). O workflow detecta os secrets e passa a: compilar → enviar o
   `.exe` ao SignPath → aguardar a assinatura → publicar a Release **já com o
   instalador assinado** (nos dois nomes, versionado e fixo). Sem os secrets,
   tudo continua funcionando como hoje (sem assinatura).

## Conferindo depois

Baixe o instalador da Release, clique com o botão direito → Propriedades →
aba **Assinaturas Digitais**: deve aparecer "SignPath Foundation" com carimbo
de tempo válido.
