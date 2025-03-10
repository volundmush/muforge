# 1. Define project scope:

## Make a list of things it can do, at a high level

## Define things it will NOT do. Bright lines you aren't allowed to creep into.

# 2. Define project components:

## Make a list of the individual servers/apps/components that make up the project

## Define the scope of each component

# 3. Define component dependencies:

## For each component, define which other components it uses, and which components use it. Make sure you don't have loops

# 4. Define component interfaces:

## For each component, define the specific needs it has from its dependencies

## This will let you then define the interfaces each component exposes

# 5. Design each component:

## Now that you know exactly what the component does, what it pulls from, and what it pushes to, define its internal structure

## Only now do you even think about what language you're using for this component.

# 6. Create a timeline:

## Write one component at a time, testing it in isolation, with dummy inputs.

## Do not write every component at once. Because you have the above, you can have fake dependencies for testing.