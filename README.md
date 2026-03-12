# MuForge

## What is this?
MuForge is the engine of the MuFoundry project, geared towards rapid and solid development of a modern take on the classic MU* games. (MUD, MUSH, MUX, MOO, etc.)

MuForge defines a `BaseApplication` class and the overall launch process, and the two core processes. A `BaseApplication` manages `Services` that run under a TaskGroup alongside it.

## The Game process
A MuFoundry game will use its `muforge.game:Application` as the main process. The Game launches a FastAPI server running on Hypercorn for both HTTP/2 and HTTP/3 support. HTTP/3 is desired for its ability to transparently reconnect roaming clients, but the game operates just fine over HTTP/2 or even HTTP/1.x.

Ideally, a MuFoundry game can be played purely by using the HTTP API and cares nothing about the client. The exact API is entirely defined by plugins, defining routers and endpoints.

## The (optional) Portal Process
There is also `muforge.portal:Application`, key to supporting legacy (telnet, etc) MU* clients. the Portal manages `Connection` objects, each representing a connected client. Protocols (defined in plugins) announce themselves by registering a link to the Portal's application, and it will then instantiate a Connection and run a startup. The Connection then speaks to the game via an `httpx` client.

## Ultimate Moddability
MuFoundry is designed to be highly moddable, loosely coupled, and very extensible.

The launch process reads .toml files from `<cwd>/config/` using `Dynaconf`, and the `Application` launch process can then choose classes, plugins, and other options from the resulting merged config.

Even the specific Application classes uses by the `Game` and `Portal` before any plugins load can be overriden in the config.

The Plugin System has its own dependency management and rich loading process, allowing each plugin to specify their own requirements and versions and interact with the core application and each other.

## Everything is a Plugin
Things provided (just with default implementation) by plugins:
- Legacy protocols (telnet, etc)
- FastAPI routers
- Database migrations
- Commands
- Portal Connection Modes ("Parsers")
- Lock Functions
- Game Systems
- Game and Portal Services
- Static file directories for the webserver.

As the Application class and plugin loading process can itself be extended, you can make plugins do just about anything.

## Related: MuPlugins
The MuFoundry project also includes a set of official plugins known as `MuPlugins`. These provide commonly used features and services from users and characters to chat channels, permissions, and more. It is assumed that most projects will at least be using `muplugins:Core` if not the entire set.

Please note, you are welcome to completely replace these with your own set, but here be dragons territory and you're largely on your own.

## Related: MuCrucible
The MuFoundry project also provides MuCrucible, which is a "project template / starting project skeleton" default implementation for creating your own MuFoundry-based game/project.
