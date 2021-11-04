var width = 960,
    height = 500

var svg = d3.select("body").append("svg")
    .attr("width", width)
    .attr("height", height);

var force = d3.forceSimulation()
    .force("charge", d3.forceManyBody().strength(-100))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("link", d3.forceLink().id(function(d) { return d.id; }).distance(30))

var voronoi = d3.voronoi()
    .x(function(d) { return d.x; })
    .y(function(d) { return d.y; })
    .extent([[0, 0], [width, height]]);

d3.json("force.json", function(error, json) {
  if (error) throw error;


  var link = svg.selectAll(".link")
      .data(json.links)
    .enter().append("line")
      .attr("class", "link");

  var node = svg.selectAll(".node")
      .data(json.nodes)
    .enter().append("g")
      .attr("class", "node")
      .call(force.drag);

  var circle = node.append("circle")
      .attr("r", 4.5);

  var label = node.append("text")
      .attr("dy", ".35em")
      .text(function(d) { return d.name; });

  var cell = node.append("path")
      .attr("class", "cell");

	force.nodes(json.nodes)
            .on("tick", ticked);
    force
            .force("link")
            .links(json.links);
  force.on("tick", function() {
    cell
        .data(voronoi(json.nodes))
        .attr("d", function(d) { return d.length ? "M" + d.join("L") : null; });

    link
        .attr("x1", function(d) { return d.source.x; })
        .attr("y1", function(d) { return d.source.y; })
        .attr("x2", function(d) { return d.target.x; })
        .attr("y2", function(d) { return d.target.y; });

    circle
        .attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; });

    label
        .attr("x", function(d) { return d.x + 8; })
        .attr("y", function(d) { return d.y; });
  });
});
