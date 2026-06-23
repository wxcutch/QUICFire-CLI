# QUICFire-CLI
Simplified QUIC-Fire simulation setup from the command line using FastFuels and GIS driven ignitions

See `scripts` for description of functionalities

# Namelist Info
All of the sections are required to be present in your namelist and variables/modes of the sections are described below. Namelists are formatted in <code>yaml</code>. See `samples` for working examples of namelist-geojson pairs. 

<div> 

<details class="popout subsection">
<summary><code>simulation</code></summary>
<hr/>
<b>Required variables:</b> 
<code>duration</code>, 
<code>saveLocation</code>

<b>Available variables:</b>
<ul>
<li><code>duration (sec)</code> - How long you would like the simulation to run for. If you want to ensure the burn totally completes, set for longer than you think necessary and the model will shut itself off when the fire is out.</li>
<li><code>title</code> - the name you would like to assign to the simulation</li>
<li><code>saveOutputVariables</code> - <code>default: ["Winds", "Energy"]</code> Names of the variables you would like the simulation to save. See the QUIC-Fire documentation for details. <code>Winds</code> is shorthand give you all of the QUIC grid averaged winds. <code>Energy</code> will give you surface energy, energy to atmosphere, and radiation products. See <a href="https://silvxlabs.github.io/quicfire-tools/reference/#quicfire_tools.inputs.SimulationInputs.set_output_files">quicfire-tools documentation</a> for variable list and description.</li>
<li><code>saveOutputFrequency (sec)</code> - <code>default: 300</code> How frequently you would like the simulation variables to be saved.</li>
<li><code>nProc</code> - <code>default: 1</code> The number of processors to run the simulation on.</li>
</ul>
</details>

<hr/>
<details class="popout subsection">
<summary><code>domain</code></summary>
<hr/>
<b>Required variables:</b>
<code>gis</code>

Gives information about the grid setup for the model

<b>Available variables:</b>
<ul>
<li><code>gis</code> - Path to your GeoJSON file for this domain. Make sure your burn unit has the property <code>"name": "BurnUnit"</code>
<li><code>horizontalGridSize (m)</code> - <code>default 2</code> The size of the square grid cells in the xy plane </li>
<li><code>verticalGridSize (m)</code> - <code>default 1</code> The size of the fire cells grid in the vertical</li>
<li><code>gisProjection</code> - <code>default "EPSG:4326"</code> The projection the GeoJSON file outlining the domain is in</li>
<li><code>atmosDepth (m)</code> - Default is quicfire-tools default or 3.25 times the difference in terrain height if the span of the terrain height values is greater than 50m.
</ul>
</details>

<hr/>
<details class="popout subsection"> 
<summary> <code>fuels</code></summary>
<hr/>
<b>Required Variables: <code>mode</code> </b>
<div style="padding-bottom: 5px;"><b>Available Modes: <code>FastFuels</code></b></div>

Information about the fuels within your domain. See the below sections for the required variables for each mode
<details class="popout subsection">
<summary><code>FastFuels</code> Mode </summary>
<b>Required variables:</b> <code>apiKey</code>
<br/>
FastFuels has 5 configurable components:
<ul>
    <li><code>topographyConfig</code></li>
    <li><code>treeConfig</code></li>
    <li><code>treeInventoryConfig</code></li>
    <li><code>featuresConfig</code></li>
    <li><code>surfaceConfig</code></li>
</ul>
Under the hood, these sections change the json requests sent to the FastFuels API via the SDK. The SDK will auto-fill any fields you leave unspecified with default values. See more information in the <a href="https://silvxlabs.github.io/fastfuels-sdk-python/v1/reference/#fastfuels_sdk.v1.convenience.export_roi">SDK documentation</a>

<div class="popout tip">
<b> Common use case: Setting surface fuel moisture </b> <br/>
Say you want to set surface fuel moisture to 8.5%. Put the following in the <code>fuels</code> section of your code. 
<pre>
surfaceConfig:
    fuelMoisture:
        source: uniform
        value: 8.5
</pre>
</div>
<aside class="popout warning"><b>Warning:</b> The FastFuels SDK documentation (as of June 2026) erroneously states to set the fuel moisture using a fraction to represent the percentage. You should use the percentage out of 100 instead. </aside>
</details>

</details>

<hr/>
<details class="popout subsection">
<summary><code>weather</code></summary>
</hr>
Describe the background wind conditions for your simulation. As of right now, only a single point definition is supported, and the observation is assumed to come from a 20' RAWS station before being used by the QUIC-Fire preprocessor.

<b>Required variables:</b> <code>windSpeed</code>, <code>windDirection</code>

</details>

<hr/>
<details class="popout subsection">
<summary><code>ignition</code></summary>
<hr/>

<b> Required variables: </b> <code>mode</code> <br/>
<b> Available modes: </b> <code>gis</code>, <code>topography</code>, <code>rectangle</code>

<details class="popout subsection">
<summary><code>gis</code></summary>
Finds a LineString with a property named <code>name = ignition</code> within your GeoJSON file describing your domain and instantaneously ignites the line at a specified width
<hr/>
<b>Variables</b>

<ul>
<li><code>timing = "instant"</code> - how you would like time to be handled by the ignition</li>
<li><code>startTime (s)</code> - <code> default 1</code> The time in the simulation to start the ignition. If you are using instantaneous ignitions this will have no effect on the simulation.</li>
<li><code>width (grid cell count)</code> - <code>default 10</code> Approximate width of the line (in grid cells) ignited from the line string</li>
</ul>
</details>

<details class="popout subsection">
<summary><code>topography</code></summary>

Finds all of the areas of an elevation between a range of heights above sea level in meters and ignites them. 
<hr/>
<b>Variables</b>

<ul>
<li><code>topElevation (m)</code> - the highest point in the range you would like to ignite</li>
<li><code>bottomElevation (m)</code> - the bottom point in the range you would like to ignite</li>
</ul>
</details>

</details>
</div>
